from transformers import AutoTokenizer, TFBertForTokenClassification, pipeline

from profilescout.common.constants import ConstantsNamespace


constants = ConstantsNamespace


class NamedEntityRecognition:
    def __init__(self, model_name=constants.NER_MODEL):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = TFBertForTokenClassification.from_pretrained(model_name)
        self.ner = pipeline('ner', model=self.model, tokenizer=self.tokenizer, framework='tf')

    def get_names(self, txt):
        ner_results = self.ner(txt)
        names = []
        curr_name = ''
        person_token_info = list(filter(lambda x: x['entity'].endswith('-PER'), ner_results))
        if len(person_token_info) == 0:
            return None

        sorted_pti = sorted(person_token_info, key=lambda x: x['start'])
        curr_name = sorted_pti[0]['word'].replace('##', '')
        for i in range(len(sorted_pti)-1):
            word = sorted_pti[i+1]['word'].replace('##', '')
            if sorted_pti[i]['end'] == sorted_pti[i+1]['start']:
                curr_name += word
            elif sorted_pti[i]['end'] + 1 == sorted_pti[i+1]['start']:
                curr_name += f' {word}' if '.' not in word else word
            else:
                mid_idx = len(curr_name)//2
                if curr_name[:mid_idx] == curr_name[mid_idx+1:]:
                    names.append(curr_name[:mid_idx])
                else:
                    names.append(curr_name)
                curr_name = word
        # handle the last name if exists
        mid_idx = len(curr_name)//2
        if curr_name[:mid_idx] == curr_name[mid_idx+1:]:
            names.append(curr_name[:mid_idx])
            names.append(curr_name[:mid_idx])
        else:
            names.append(curr_name)
        two_surnames_included = [names[-1]] if names else []
        for i in range(len(names)-1):
            possible_two_sn = f'{names[i]}-{names[i+1]}'
            if possible_two_sn in txt:
                two_surnames_included += [possible_two_sn]
            else:
                two_surnames_included += [names[i]]
        return two_surnames_included
