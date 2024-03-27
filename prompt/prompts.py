from string import Template

class PromptGenerator(object):  
    def __init__(self, session_info, bundle_info):
        self.bundle_info = bundle_info
        self.session_info = session_info

    # def get_prompt(self):
    #     if self.prompt_type == 'Init_generated_bundles':
    #         return get_Intents_generated_bundles(self.session_info)
    #     elif self.prompt_type == 'Self_correction':
    #         return get_Self_correction(self.session_info)
    #     elif self.prompt_type == 'Feedback':
    #         return get_Feedback(self.session_info)
    #     else:
    #         raise ValueError('Invalid prompt type')

    def get_Intents_generated_bundles(self, session_info):
        Init_generated_bundles = """A bundle can be a set of alternative or complementary products that are purchased with a certain intent. 
    Please detect bundles from a sequence of products. Each bundle must contain multiple products. 
    Here are the products and descriptions: $session_info. The answer format is: {'bundle number':['product number']}.
    No explanation for the results is needed."""

        return Template(Init_generated_bundles).substitute(session_info=session_info)

    def get_Self_correction(self, idx):
        Self_correction = ["Please use 3 to 5 words to generate intents behind the detected bundles, the output format is: {'bundle number':'intent'}.",
                        "Given the generated intents, adjust the detected bundles with the product descriptions. The output format is: {'bundle number':'product number'}.",
                        "Given the adjusted bundles, regenerate the intents behind each bundle, the output format is: {'bundle number':'intent'}."]
        
        return Self_correction[idx]

    def get_Feedback(self, type, error_dict=None, intent_feedback=None):
        if type == 'bundle':
            prefix_feedback =  "Here are some tips for the detected bundles in your answer: "
            error_types = ['correct and should be remained. ',
                    'invalid and should be removed. ',
                    'containing some irrelevant products that should be removed. ',
                    'missing some products and should append other related products from the sequence. ',
                    'missing some products and should contain at least 2 related products. '] 
            suffix_tips = "Adjust the bundles based on the tips in your answer. Please output the adjusted bundles with the format: {'bundle number':'product number'}."

            feed_tips = prefix_feedback
            for error in sorted(error_dict.keys()):
                if len(error_dict[error]) > 1:
                    feed_tips += ' and '.join(error_dict[error]) +' are '+ error_types[error]
                else:
                    feed_tips += error_dict[error][0] +' is '+ error_types[error]
            feed_tips += suffix_tips


            return feed_tips
        
        elif type == 'intent':
            intent_prompts = """
                Here are some tips for the generated intents in your answer: $intent_feedback
                Please output the regenerated intents with the format: {'bundle number':'intent'}.
                """
            error_types = ['be more natural', 'cover more products within the bundle', 'have more motivational description']

            intent_feedback_prompt = ''
            for bundle_id, aspects in intent_feedback.items():
                if len(aspects)>0:
                    intent_feedback_prompt += 'for bundle' + str(bundle_id+1)
                    intent_feedback_prompt += ', regenerate the intent to '
                    intent_feedback_prompt += ' and '.join([error_types[aspect] for aspect in aspects]) + '. '

            return Template(intent_prompts).substitute(intent_feedback=intent_feedback_prompt)
    
    def get_Intent_rater(self, related_bundles, item_titles):
        prompts_template = '''
            The intent should describe the customer motivation well in the purchase of the product bundles. You are asked to evaluate with two intents for a bundle, using three metrics: Naturalness, Coverage, and Motivation. The details and scales of each metric are listed below:
            Naturalness:
            1-the intent is difficult to read and understand.
            2-the intent is fair to read and understand.
            3-the intent is easy to read and understand.
            Coverage:
            1-only a few items in the bundle are covered by the intent.
            2-around half items in the bundle are covered by the intent.
            3-most items in the bundle are covered by the intent.
            Motivation:
            1-the intent contains no motivational description.
            2-the intent contains motivational description.

            Following are the bundles that we ask you to evaluate:
            $bundle_info
            Please answer in the following format: {'bundle number': {'intent number':
            ['Naturalness score', 'Coverage score', 'Motivation score']}}.
            No explanation for the result.
            '''
        meta_info ={}
        for test_id, (topk_session_idx, related_infos) in related_bundles.items():
            all_info = []
            for bundle_info in related_infos:
                idx_item_titles = {}
                for idx, item_id in enumerate(bundle_info[0].split(',')):
                    idx_item = "product" + str(idx+1)
                    idx_item_titles[idx_item] = item_titles[item_id]
                
                idx_intent = {}
                idx_intent['intent1'] = bundle_info[1]
                idx_intent['intent2'] = bundle_info[-1]
                all_info.append((str(idx_item_titles), str(idx_intent)))
            meta_info[test_id] = all_info

        intent_rater_prompt = {}
        for test_id, all_info in meta_info.items():
            bundle_info = ''
            for idx, info in enumerate(all_info):
                bundle_info += 'Bundle' + str(idx+1) + ': ' + info[0] +'\n'+ info[1] + '\n'
            intent_rater_prompt[test_id] = Template(prompts_template).substitute(bundle_info=bundle_info)

        return intent_rater_prompt
    
    def get_test_prompts(self, data_info):
        test_prompts = "Based on the rules, detect bundles for the below product sequence:\n"
        
        test_item_titles = {}

        for idx, item_title in enumerate(data_info.split('|')):
            idx_item = "product" + str(idx+1)
            test_item_titles[idx_item] = item_title
        test_prompts += str(test_item_titles) + '\n'
        test_prompts += ", the answer format is: {'bundle number':['product number']}. No explanation for the results."


        return test_prompts
