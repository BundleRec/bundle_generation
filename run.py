import numpy as np
import yaml
from utils.ChatAPI import OpenAI, Claude
from utils.logger import Logger
from utils.functions import output_parser, process_results
from utils.metrics import findErrors, compute
from prompt.prompts import PromptGenerator
from tqdm import tqdm
import argparse
 

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str, default='electronic')
opt = parser.parse_args()

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

if __name__ == '__main__':
     
    logger = Logger(config['log_path'])
    data_path = config['data_path']+opt.dataset+'/'
    temp_path = config['temp_path']+opt.dataset+'/'
    train_set = np.load(f'{data_path}training_set.npy', allow_pickle=True).item()
    test_set = np.load(f'{data_path}test_set.npy', allow_pickle=True).item()
    k_neareast_sessions = np.load(f'{data_path}TopK_related_sessions.npy', allow_pickle=True).item()
    session_items = np.load(f'{data_path}session_items.npy', allow_pickle=True).item()
    session_bundles = np.load(f'{data_path}session_bundles_deduplication.npy', allow_pickle=True).item()
    all_item_titles = np.load(f'{data_path}item_titles.npy', allow_pickle=True).item()

    # Create a new OpenAI instance
    chat = OpenAI(config['model'], config['api_key'], config['temperature'])
    # Create a new prompt generator
    prompt_generator = PromptGenerator(session_items, session_bundles)

    # Construct meta info for training sessions
    prompt_generated_bundles = {} 

    for test_id in test_set.keys():
        topk_session_idx = k_neareast_sessions[test_id][0]  # consider top-1 related session
        item_titles = train_set[topk_session_idx]
        idx_item_titles = {}
        for idx, item_title in enumerate(item_titles.split('|')):
            idx_item = "product" + str(idx+1)
            idx_item_titles[idx_item] = item_title

        prompt = prompt_generator.get_Intents_generated_bundles(str(idx_item_titles))
        prompt_generated_bundles[test_id] = (topk_session_idx, prompt)

    logger.info('Start generating bundles with self-correction...')
    self_correction_res = {}
    for test_id, (topk_session_idx, prompt) in tqdm(prompt_generated_bundles.items()):
        message = [{"role": "user", "content": prompt}]
        init_res = chat.create_chat_completion(message)
        message.append({"role": "assistant", "content": init_res})
        for i in range(3):
            message.append({"role": "user", "content": prompt_generator.get_Self_correction(i)})
            intent_res = chat.create_chat_completion(message)
            message.append({"role": "assistant", "content": intent_res})
            # early stop if the bundle is not changed
            if i == 1 and init_res == intent_res:
                break
        self_correction_res[test_id] = (topk_session_idx, message)

    np.save(f'{temp_path}self_correction_res.npy', self_correction_res, allow_pickle=True)

    parsered_res = dict()
    for test_id, (topk_session_idx, message) in tqdm(self_correction_res.items()):

        if len(message) == 6:
            bundle_str = message[-1]['content'].replace('\n', '')
        elif len(message) == 8:
            bundle_str = message[-3]['content'].replace('\n', '')
        output_parser_res = output_parser(bundle_str)
        if output_parser_res['state_code'] == 404:
            logger.warning(f'Error when parsering test_id: {test_id}')
            continue
        elif output_parser_res['state_code'] == 200:
            bundle_dict = output_parser_res['output']
            parsered_res[test_id] = (topk_session_idx, bundle_dict)
    
    logger.info('Start generating bundle feedback...')

    feedback_res = {}
    N_iter = config['feedback_iteration']
    
    for test_id, (topk_session_idx, bundle_dict) in tqdm(parsered_res.items()):
        Is_hallucination = False
        context = self_correction_res[test_id][1].copy()
        # iterately generate feedback for N times
        for _ in range(N_iter):

            error_dict = findErrors(topk_session_idx, bundle_dict, session_bundles, session_items)
            if 0 in error_dict and len(error_dict)==1:
                feedback_res[test_id] = self_correction_res[test_id]
                break
            elif 5 in error_dict:
                # hallucination
                Is_hallucination = True
                break      
            else:
                # Get the prompt
                feedback_prompt = prompt_generator.get_Feedback('bundle', error_dict)
                context.append({"role": "user", "content": feedback_prompt})
                # Create a new chat completion
                reply_str = chat.create_chat_completion(context)
                context.append({"role": "assistant", "content": reply_str})
                output_parser_res = output_parser(reply_str)
                if output_parser_res['state_code'] == 200:
                    bundle_dict = output_parser_res['output']
        if not Is_hallucination:
            feedback_res[test_id] = (topk_session_idx, context)

    np.save(f'{temp_path}feedback_res.npy', feedback_res, allow_pickle=True)

    logger.info('Start generating intent feedback...')

    # Generate intent for matched bundles
    intent_context = {}

    for test_id, (topk_session_idx, context) in tqdm(feedback_res.items()):
        if len(context) == 8:  # no feedback
            intent_context[test_id] = (topk_session_idx, context)
            continue
        append_intent_context = context.copy()
        append_intent_context.append({"role": "user", "content": "Given the adjusted bundles, regenerate the intents behind each bundle, the output format is: {'bundle number':'intent'}."})
        intent_str = chat.create_chat_completion(append_intent_context)
        append_intent_context.append({"role": "assistant", "content": intent_str})
        intent_context[test_id] = (topk_session_idx, append_intent_context)
    
    np.save(f'{temp_path}intent_context.npy', intent_context, allow_pickle=True)

    intent_related_bundles = {}
    for test_id, (topk_session_idx, context) in intent_context.items():
        bundle_res = output_parser(context[-3]['content'])
        intent_res = output_parser(context[-1]['content'], type='intent')
        items_session = session_items[topk_session_idx].split(',')
        ground_truth_bundles = session_bundles[topk_session_idx]

        if bundle_res['state_code'] == 404:
            logger.warning(f'Error when parsering test_id: {test_id}')
            continue
        elif bundle_res['state_code'] == 200:
            bundle_dict = bundle_res['output']
            intent_dict = intent_res['output']
            related_bundles = []
            for bundle_id, items in bundle_dict.items():
                if len(items) < 2:
                    # logger.warning(f'Empty result in test_id: {test_id}')
                    continue
                reidx_items = set([items_session[int(item[-1])-1] for item in items])
                for gdbundle in ground_truth_bundles:
                    bundle_list = set(gdbundle[-1].split(','))
                    if reidx_items <= bundle_list:
                        if 'bundle' in bundle_id and len(bundle_id) < 10:
                            related_bundles.append((','.join(list(reidx_items)), intent_dict[bundle_id], gdbundle[-1], gdbundle[0]))
                        else: # intent:bundle
                            related_bundles.append((','.join(list(reidx_items)), bundle_id, gdbundle[-1], gdbundle[0]))
                        break
            if len(related_bundles) != 0:
                intent_related_bundles[test_id] = (topk_session_idx, related_bundles)

    # Generate intent feedback
    intent_feedback_generation = prompt_generator.get_Intent_rater(intent_related_bundles, all_item_titles)
    np.save(f'{temp_path}intent_feedback_generation.npy', intent_feedback_generation, allow_pickle=True)

    logger.info('Rating for generated intent...')

    intent_feedback_res = {}
    intent_rater_models = config.get('intent_raters', [])
    intent_raters = []
    for rate_model in intent_rater_models:
        if 'openai' in rate_model:
            intent_raters.append(OpenAI(rate_model['openai']['model'], rate_model['openai']['api_key'], rate_model['openai']['temperature']))
        elif 'claude' in rate_model:
            intent_raters.append(Claude(rate_model['claude']['model'], rate_model['claude']['api_key'], rate_model['claude']['temperature']))
        else:
            raise Exception('No such model')
    for test_id, (topk_session_idx, related_bundles) in tqdm(intent_related_bundles.items()):
        metric_scores = []
        
        for rater in intent_raters:
            message = [{"role": "user", "content": intent_feedback_generation[test_id]}]
            # rate for 3 times
            scores_res = {}
            for _ in range(3):
                intent_feedback_str = rater.create_chat_completion(message)
                intent_res = output_parser(intent_feedback_str, type='intent')['output']
                for idx, (bid, intent) in enumerate(intent_res.items()):
                    if idx not in scores_res:
                        scores_res[idx] = [np.array([0,0,0]), np.array([0,0,0])]
                    key_list = list(intent.keys())
                    scores_res[idx][0] += np.array([int(i) for i in intent[key_list[0]]]) #intent 1
                    scores_res[idx][1] += np.array([int(i) for i in intent[key_list[1]]]) #intent 2
            metric_scores.append(scores_res)

        # get the final score
        lower_bundle = {}
        for bundle_id in metric_scores[0]:
            intent1_score = metric_scores[0][bundle_id][0] # prediction intent
            intent2_score = metric_scores[0][bundle_id][1] # truth intent
            res_rater1 = [i for i, (a, b) in enumerate(zip(intent1_score, intent2_score)) if a < b]

            intent1_score = metric_scores[1][bundle_id][0]
            intent2_score = metric_scores[1][bundle_id][1]
            res_rater2 = [i for i, (a, b) in enumerate(zip(intent1_score, intent2_score)) if a < b]

            merged_res = list(set(res_rater1 + res_rater2))
            if len(merged_res) > 0:
                lower_bundle[bundle_id] = merged_res

        if len(lower_bundle) > 0:
            intent_feedback_prompt = prompt_generator.get_Feedback('intent', intent_feedback=lower_bundle)
            context = intent_context[test_id][1].copy()
            context.append({"role": "user", "content": intent_feedback_prompt})
            intent_feedback_str = chat.create_chat_completion(context)
            context.append({"role": "assistant", "content": intent_feedback_str})
            intent_feedback_res[test_id] = (topk_session_idx, context)

        else:
            intent_feedback_res[test_id] = intent_context[test_id]

    np.save(f'{temp_path}intent_feedback_res.npy', intent_feedback_res, allow_pickle=True)

    logger.info('Start generating bundles for test sessions...')
    # merge all sessions
    merged_context = {}
    for test_id, (topk_session_idx, context) in tqdm(intent_context.items()):
        if test_id in intent_feedback_res:
            merged_context[test_id] = intent_feedback_res[test_id]
        else:
            merged_context[test_id] = intent_context[test_id]

    All_context = {}
    for test_id, (topk_session_idx, context) in tqdm(merged_context.items()):
        test_context = context.copy()
        test_context.append({"role": "user", "content": "Based on conversations above, which rules do you find when detecting bundles?"})
        rule_str = chat.create_chat_completion(test_context)
        test_context.append({"role": "assistant", "content": rule_str})

        test_prompt = prompt_generator.get_test_prompts(test_set[test_id])
        test_context.append({"role": "user", "content": test_prompt})
        test_str = chat.create_chat_completion(test_context)
        test_context.append({"role": "assistant", "content": test_str})
        test_context.append({"role": "user", "content": "Please use 3 to 5 words to generate intents behind the detected bundles, the output format is: {'bundle number':'intent'}"})
        intent_str = chat.create_chat_completion(test_context)
        test_context.append({"role": "assistant", "content": intent_str})
        
        All_context[test_id] = (topk_session_idx, test_context)


    logger.info('Evaluating the generated bundles...')
    bundle_res = {}

    for test_id, (topk_session_idx, context) in tqdm(All_context.items()):
        parsered_res = output_parser(context[-3]['content'])

        if parsered_res['state_code'] == 404:
            logger.warning(f'Error when evaluating test_id: {test_id}')
            continue 
        bundle_res[test_id] = parsered_res['output']

    np.save(f'{temp_path}bundle_res.npy', bundle_res, allow_pickle=True)

    # remove the bundles containing only 1 product
    format_res = process_results(bundle_res)
    
    session_precision, session_recall, coverage = compute(session_items, session_bundles, format_res)
    print(f'Precision: {session_precision}, Recall: {session_recall}, Coverage: {coverage}')
    



                            
            


