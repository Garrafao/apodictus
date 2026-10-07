from vllm import LLM, SamplingParams

def generate_definitions(prompts, model_name, sampling_dict):
    sampling_params = SamplingParams(**sampling_dict)
    llm = LLM(model=model_name)
    outputs = llm.generate(prompts, sampling_params)
    return outputs