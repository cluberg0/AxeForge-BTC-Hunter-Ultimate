static turbo::Reason turbo_wall_reason()
{
    switch(g_state.tuner.wall){
    case TunerWall::Power:return turbo::Reason::Power;
    case TunerWall::Thermal:return turbo::Reason::Thermal;
    case TunerWall::Errors:return turbo::Reason::Errors;
    case TunerWall::MvGate:return turbo::Reason::Voltage;
    case TunerWall::Hold:return turbo::Reason::Hold;
    default:return turbo::Reason::Frequency;
    }
}
static void run_turbo_phase()
{
    turbo::Point anchor;if(!turbo::begin(anchor))return;
    const TunerState previous=g_state.tuner;
    uint16_t f=anchor.mhz,mv=anchor.mv;float ghs=anchor.ghs;
    fresh_readout();
    bool good=climb(f,mv,ghs);
    auto reason=turbo::reason();
    bool can_hold=good&&!turbo::cancelled();
    if(!can_hold&&board::is_powered()&&(reason==turbo::Reason::Power||reason==turbo::Reason::Errors)){
        auto prior=turbo::fallback(uint16_t(board::freq_mhz()+1),turbo::power_budget());
        if(prior.watts<=turbo::power_budget()*.95f&&apply(prior.mhz,prior.mv,true)){
            f=prior.mhz;mv=prior.mv;ghs=prior.ghs;turbo::holding(reason);can_hold=!turbo::cancelled();
        }
    }
    if(can_hold){
        if(!apply(f,mv,true))can_hold=false;
        else turbo::holding(reason==turbo::Reason::None?turbo_wall_reason():reason);
    }
    while(can_hold&&board::is_powered()&&!s_restart&&settings::get().autotune){
        g_state.tuner.phase=TunerPhase::Locked;
        snprintf(g_state.tuner.note,sizeof(g_state.tuner.note),"TURBO held %u MHz @ %u mV; explicit stop returns stock",f,mv);
        auto r=measure(0,WATCH_WINDOW_S,MAX_ERR_PCT,WORST_CHIP_PCT);
        if(r.verdict==Verdict::Stable)continue;
        reason=turbo::reason();
        if(reason==turbo::Reason::None||reason==turbo::Reason::Frequency||reason==turbo::Reason::Voltage||reason==turbo::Reason::Hold)
            reason=r.verdict==Verdict::Power?turbo::Reason::Power:r.verdict==Verdict::Thermal?turbo::Reason::Thermal:turbo::Reason::Errors;
        if(reason==turbo::Reason::Errors||reason==turbo::Reason::Power){
            auto prior=turbo::fallback(f,turbo::power_budget());
            if(prior.mhz<f&&prior.watts<=turbo::power_budget()*.95f&&apply(prior.mhz,prior.mv,true)){
                f=prior.mhz;mv=prior.mv;turbo::holding(reason);continue;
            }
        }
        break;
    }
    if(reason==turbo::Reason::None)reason=turbo::reason();
    if(reason==turbo::Reason::None)reason=turbo::Reason::Settings;
    turbo::stop(reason);
    if(board::is_powered()&&!apply(anchor.mhz,anchor.mv,true))board::shutdown();
    turbo::finish();
    if(board::is_powered())g_state.tuner=previous;
    // Never persist a Turbo frequency, cap or armed flag into stock settings.
}
