// Same stock tuner task and apply/measure functions; no additional controller.
static bool turbo_confirm(Result&r,uint16_t f,uint16_t&mv)
{
    Result repeat=measure(WARMUP_S/2,WINDOW_S,MAX_ERR_PCT,WORST_CHIP_PCT);
    if(repeat.verdict!=Verdict::Stable){if(!turbo::cancelled())turbo::stop(repeat.verdict==Verdict::Thermal?turbo::Reason::Thermal:repeat.verdict==Verdict::Power?turbo::Reason::Power:turbo::Reason::Errors);return false;}
    if(fminf(r.ghs,repeat.ghs)<fmaxf(r.ghs,repeat.ghs)*.95f){turbo::stop(turbo::Reason::Errors);return false;}
    r.ghs=fminf(r.ghs,repeat.ghs);r.pmax=fmaxf(r.pmax,repeat.pmax);
    r.tmax=fmaxf(r.tmax,repeat.tmax);r.vrmax=fmaxf(r.vrmax,repeat.vrmax);
    // Find the lowest measured stable voltage at this PLL point, no bypass of gates.
    while(mv>=board::clamp_mv(0)+MV_STEP){
        uint16_t prior=mv,candidate=uint16_t(mv-MV_STEP);
        if(!apply(f,candidate))return false;
        auto lower=measure(WARMUP_S,WINDOW_S,MAX_ERR_PCT,WORST_CHIP_PCT);
        if(lower.verdict==Verdict::Stable){auto confirm=measure(WARMUP_S/2,WINDOW_S,MAX_ERR_PCT,WORST_CHIP_PCT);if(confirm.verdict!=Verdict::Stable)lower=confirm;else {lower.ghs=fminf(lower.ghs,confirm.ghs);lower.pmax=fmaxf(lower.pmax,confirm.pmax);}}
        if(lower.verdict==Verdict::Stable){mv=candidate;r=lower;continue;}
        if(lower.verdict!=Verdict::Errors||turbo::cancelled())return false;
        if(!apply(f,prior,true))return false;
        auto verify=measure(WARMUP_S,WINDOW_S,MAX_ERR_PCT,WORST_CHIP_PCT);
        if(verify.verdict!=Verdict::Stable)return false;
        r=verify;break;
    }
    return true;
}
