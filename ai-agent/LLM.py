from transformers import AutoTokenizer, AutoModelForCausalLM

SYSTEM_PROMPT = (
    "Используя только предоставленный контекст из документов, дай краткий и точный ответ на вопрос пользователя."
    "Если контекст не содержит ответа — сообщи об этом."
)

class LLM:
    def __init__(self, model="./model/decoder-encoder", device="cpu"):
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(model).to(device)
        self.device = device

    def generate_answer(self, question, context):
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Контекст:\n{context}\n\n"
            f"Вопрос: {question}\nОтвет:"
        )

        inputs = self.tokenizer(prompt, return_tensors="pt", padding=True, truncation=True).to(self.device)

        output = self.model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False,
            temperature=1.0,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.eos_token_id
        )

        decoded = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return decoded.split("Ответ:", 1)[-1].strip()