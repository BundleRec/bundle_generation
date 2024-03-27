import re
import ast

def output_parser(response_str, type='bundle'):
    state_code = 0
    response_str = response_str.replace('\n', '')
    if type == 'bundle':
        if '[' in response_str:
            if not response_str.startswith('{'):
                match_str = re.search(r'{.*}', response_str, re.DOTALL)
                match_str = match_str.group().replace('\n', '')
                if "}{" in match_str:
                    match_str = match_str.replace("}{", ", ")
                response_str = match_str
            response_dict = ast.literal_eval(response_str)
            state_code = 200
        else:
            state_code = 404
            response_dict = {}
    elif type == 'intent':
        if not response_str.startswith('{'):
            match_str = re.search(r'{.*}', response_str, re.DOTALL)
            match_str = match_str.group().replace('\n', '')
            response_str = match_str
        if "}{" in response_str:
            response_str = response_str.replace("}{", ", ")
        response_dict = ast.literal_eval(response_str)
        state_code = 200

    return {'state_code': state_code, 'output': response_dict}

def process_results(bundle_res):
    invalid_id = []
    for testid, bundles in bundle_res.items():
        c = 0
        for b,items in bundles.items():
            if len(items)==1:
                c+=1
        # print(c, len(bundles))
        if c==len(bundles):
            # print(test_id)
            invalid_id.append(testid)
    print(invalid_id)

    remove_invalid_res = {}
    for test_id, bundles in bundle_res.items():
        if test_id in invalid_id:
            continue
        format_bundles = {}
        for bid, items in bundles.items():
            if len(items)>1:
                format_bundles[bid] = items
        remove_invalid_res[test_id] = format_bundles

    return remove_invalid_res