from nltk.corpus import wordnet as wn
import pandas as pd


sentence_limit_size=1000

def get_definitions_for_word(word):
    synsets = wn.synsets(word)
    return [f"{i+1}. {synset.definition()}" for i, synset in enumerate(synsets)]

def create_definitions_text(word):
    definitions = get_definitions_for_word(word)
    return f"Definitions of '{word}':\n" + "\n".join(definitions) if definitions else ""

def build_prompt(target_word, sentence, use_wordnet=True):
    wordnet_defs = create_definitions_text(target_word) if use_wordnet else ""
    return f"""
Context:
Imagine you are Mike an expert in Gloss and sense definition generation. 
You just require a target word and a sentence to generate understandable and informative definition.
You are a professional and have been doing this for years.
Your ability for generating definitions for human readability and machine understanding is unmatched.
You are a very precise expert and will not generate any additional text besides the definition.
Mike can't make any mistakes since he is a professional and many researchers depend on his expertise.

TASK:
Generate a definition for target word from given sentence. 
Make the definition human readable and informative aswell.
Do not just copy the definition from the given Dictionary, but rather use it as a reference to create a more human-readable and informative definition.

Follow the following steps:
1. Read the target word and sentence.
2. If Available read the definitions of the target word from Dictionary.
3. Understand the context of the target word in the sentence.
4. Generate a definition that is clear, concise, and informative.

Now solve the task for:
Target Word: {target_word}
Sentence: {sentence}
Dictionary Definitions: {wordnet_defs}
Output:
"""

def build_prompt_group(grouped_dataset):
    prompts = []
    all_sentences = []
    # Iterate over each group in the dataset
    for sense_id, group in grouped_dataset:
        target_word = group['lemma'].iloc[0]
        sentences_list = group['context'].tolist()
        sentences=""
        for sentence in sentences_list:
            if len(sentences)<sentence_limit_size:
                sentences += sentence + " NEXT SENTENCE: "
        #print(f"LAST STEP!!!: Processing sense_id: {sense_id}, target_word: {target_word}, sentences: {sentences}")
        all_sentences.append(sentences)
        prompts.append(f"""
Context:
Imagine you are Mike an expert in Gloss and sense definition generation. 
You just require a target word and sentences to generate understandable and informative definition.
You are a professional and have been doing this for years.
Your loved for generating definitions for human readability and machine understanding is unmatched.
You are a very precise expert and will not generate any additional text besides the definition.
Mike can't make any mistakes since he is a professional and many researchers depend on his expertise.

TASK:
Generate a definition for target word from given sentences. 
Make the definition human readable and informative aswell.
Do not just copy the definition from WordNet, but rather use it as a reference to create a more human-readable and informative definition.

Follow the following steps:
1. Read the target word and sentences.
2. If Available read the definitions of the target word from WordNet.
3. Understand the context of the target word in the sentences.
4. Generate a definition that is clear, concise, and informative.

Now solve the task for:
Target Word: {target_word}
Sentence: {sentences}
WordNet Definitions:
Output:
        """)
    return prompts, all_sentences
        


def build_prompt_improve_existing_def(definition_df):
    prompts=[]
    for index, row in definition_df.iterrows():
        target_word = row['lemma']
        definition = row['definition']
        prompts.append(f"""Context:
Imagine you are Mike an expert in Gloss and sense definition generation. 
You just require a target word and sentences to generate understandable and informative definition.
You are a professional and have been doing this for years.
Your loved for generating definitions for human readability and machine understanding is unmatched.
You are a very precise expert and will not generate any additional text besides the definition.
Mike can't make any mistakes since he is a professional and many researchers depend on his expertise. Create a more human-readable and informative definition for the word '{target_word}' based on the existing definition: '{definition}'.\nOutput:
""")
    return prompts


def build_prompt_lem_group(grouped_dataset, definition_df):
    prompts = []
    # Iterate over each group in the dataset
    for sense_id, group in grouped_dataset:
        target_word = group['lemma'].iloc[0]
        sentences_list = group['context'].tolist()
        sentences=""
        for sentence in sentences_list:
            if len(sentences)<sentence_limit_size:
                sentences += sentence + " NEXT SENTENCE: "
        #print(f"Processing sense_id: {sense_id}, target_word: {target_word}, sentences: {sentences}")

        # map group sense_id to definition_df sense_id and get the definition
        definition_row = definition_df[definition_df['sense_id'] == sense_id]
        definition = definition_row['definition'].iloc[0] if not definition_row.empty else "No definition found"

        prompts.append(f"""Context:
Imagine you are Mike an expert in Gloss and sense definition generation. 
You just require a target word and sentences to generate understandable and informative definition.
You are a professional and have been doing this for years.
Your loved for generating definitions for human readability and machine understanding is unmatched.
You are a very precise expert and will not generate any additional text besides the definition.
Mike can't make any mistakes since he is a professional and many researchers depend on his expertise. Create a more human-readable and informative definition for the word '{target_word}' based on the existing definition: '{definition}' and retrieved usages '{sentences}'.\nOutput:
""")
    return prompts


def build_prompt_llm_based_wsd(dataset, def_column_name, lemur_definitions):
    prompts=[]
    for index, row in dataset.iterrows():
        #find row in lemur_definitions with same sense_id
        definition_row = lemur_definitions[lemur_definitions['sense_id'] == row['sense_id']]
        target_word = row['lemma']
        sentence = row['context']
        #definition_row = definition_df[definition_df['sense_id'] == row['sense_id']]
        definitions=""
        # create definitions text from definition_row by adding sense_id and definition
        #for _, def_row in definition_row.iterrows():
        #    definitions += f"Sense_id: {def_row['sense_id']}: {def_row[def_column_name]} "
        for column in def_column_name:
            definitions += f"@@{column}##: {definition_row[column]} "
        prompts.append(f"""Given the target word '{target_word}' and the following definitions:{definitions}.\n Assign the most fitting definition to the Sentence:'{sentence}'\n Output only the name of the sense inside the @@ and ## symbols you chose to use. You are not allowed to add any additional text and you always have to choose one of the proposed senses!""")
        
    
    return prompts

#todo
def build_prompt_llm_def_decision(dataset, def_column_name, lemur_definitions):
    prompts=[]
    for index, row in lemur_definitions.iterrows():
        definition_row = lemur_definitions[lemur_definitions['sense_id'] == row['sense_id']]
        target_word = row['lemma']
        #sentence = row['context']
        #definition_row = definition_df[definition_df['sense_id'] == row['sense_id']]
        definitions=""
        # create definitions text from definition_row by adding sense_id and definition
        #for _, def_row in definition_row.iterrows():
        #    definitions += f"Sense_id: {def_row['sense_id']}: {def_row[def_column_name]} "
        for column in def_column_name:
            definitions += f"@@{column}##: {definition_row[column]} "
        prompts.append(f"""Given the target word '{target_word}', the start definition @@definition##: {definition_row['definition']} and the following generated definitions:{definitions}.\n Select the best describing and fitting definition in relation to the start definition.'\n Output only the name of the sense inside the @@ and ## symbols you choose. You are not allowed to add any additional text and you always have to choose one of the proposed senses or the start definition!""")
        
    
    return prompts
    
