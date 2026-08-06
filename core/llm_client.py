"""OpenAI 兼容格式的大模型客户端。"""

from __future__ import annotations

from openai import OpenAI

from src.config import Settings, settings


class LLMClient:
    def __init__(self, config: Settings = settings):
        config.validate_llm()
        self.config = config
        # self.client = OpenAI(
        #     api_key=config.api_key,
        #     base_url=config.base_url,
        # )
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=60.0,
            max_retries=2,)
        self.total_tokens = 0

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        thinking: bool = False,
    ) -> str:
        request_params = {
            "model": self.config.model_name,
            "messages": messages,
        }

        # DeepSeek支持按请求开启或关闭思考模式
        if "api.deepseek.com" in self.config.base_url:
            if thinking:
                request_params["reasoning_effort"] = "high"
                request_params["extra_body"] = {
                    "thinking": {
                        "type": "enabled"
                    }
                }
            else:
                request_params["temperature"] = temperature
                request_params["extra_body"] = {
                    "thinking": {
                        "type": "disabled"
                    }
                }
        else:
            # 保持对其他OpenAI兼容接口的支持
            request_params["temperature"] = temperature

        response = self.client.chat.completions.create(
            **request_params
        )

        if response.usage:
            self.total_tokens += response.usage.total_tokens

        return response.choices[0].message.content or ""

    def token_usage(self) -> dict[str, int | str]:
        return {
            "model": self.config.model_name,
            "total_tokens": self.total_tokens,
        }

