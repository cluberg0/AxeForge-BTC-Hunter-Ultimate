#!/usr/bin/env python3
"""Check native route protection, documented source keys and real host API output.

Run after apply.py. --json-dir optionally validates API_JSON lines captured from
native host tests against the OpenAPI schemas (requires jsonschema).
"""
import argparse
import copy
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def property_names(schema):
    result = set(schema.get('properties', {}))
    for value in schema.get('properties', {}).values():
        result |= property_names(value)
    if 'items' in schema:
        result |= property_names(schema['items'])
    return result


def json_schema(schema):
    """Convert OpenAPI 3 nullable to JSON Schema draft 7 for runtime checks."""
    schema = copy.deepcopy(schema)
    if isinstance(schema, list):
        return [json_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    schema = {key: json_schema(value) for key, value in schema.items()}
    if schema.pop('nullable', False):
        return {'anyOf': [schema, {'type': 'null'}]}
    return schema


def check(source_root, json_dir=None):
    import yaml
    reference = json.loads((ROOT / 'overlay/docs/native-api.json').read_text())
    merged = yaml.safe_load((source_root / 'docs/openapi.yaml').read_text())
    web = (source_root / 'main/net/web.cpp').read_text()
    assert 'u.handler = api_guard;' in web and 'strncmp(u.uri, "/api/", 5) == 0' in web
    assert 'otp::session_ok(tok)' in web and 'origin_matches(v, host)' in web
    for path, methods in reference['paths'].items():
        module = 'hunter' if path.endswith('hunter') else 'intelligence'
        namespace = 'hunter' if module == 'hunter' else 'intel'
        source = (source_root / f'main/core/{module}.cpp').read_text()
        for method, spec in methods.items():
            assert merged['paths'][path][method] == spec, (path, method, 'merged documentation differs')
            function = 'get' if method == 'get' else 'set'
            registration = f'{{"{path}", HTTP_{method.upper()}, {namespace}::{function}, NULL}}'
            assert registration in web, (path, method, 'route missing or bypasses expected handler')
            if method == 'get':
                schema = spec['responses']['200']['content']['application/json']['schema']
                sent_keys = set(re.findall(r'\\"(\w+)\\"\s*:', source))
                assert sent_keys == property_names(schema), (path, 'response keys', sent_keys ^ property_names(schema))
            else:
                schema = spec['requestBody']['content']['application/json']['schema']
                read_keys = set(re.findall(r'cJSON_GetObjectItem\([^,]+,\s*"(\w+)"\)', source))
                assert read_keys == set(schema['properties']), (path, 'POST keys', read_keys ^ set(schema['properties']))
                assert spec['security'] == [{'csrf': [], 'session': []}]
        if json_dir:
            import jsonschema
            data = (json_dir / (module + '.log')).read_text()
            lines = [line.removeprefix('API_JSON ') for line in data.splitlines() if line.startswith('API_JSON ')]
            assert lines, (module, 'host test emitted no API_JSON line')
            schema = json_schema(methods['get']['responses']['200']['content']['application/json']['schema'])
            jsonschema.Draft7Validator.check_schema(schema)
            for line in lines:
                jsonschema.validate(json.loads(line), schema)
        print('native API contract:', path, 'source/schema/guard OK' + ('; host JSON OK' if json_dir else ''))
    print('PASS: both native endpoints are documented and use the stock API guard')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source_root', type=pathlib.Path, nargs='?', default=ROOT / 'upstream')
    p.add_argument('--json-dir', type=pathlib.Path)
    args = p.parse_args()
    try:
        check(args.source_root.resolve(), args.json_dir)
    except (AssertionError, KeyError, ValueError) as error:
        sys.exit(str(error))
