import aiohttp


class BitrixError(Exception):
    pass


class BitrixClient:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.rstrip("/") + "/"

    async def call(self, method: str, params: dict | None = None) -> dict:
        """
        Универсальный вызов метода Bitrix24 REST API.

        Например:
        method = "crm.deal.add"
        итоговый URL будет:
        https://.../rest/1/key/crm.deal.add.json
        """
        url = f"{self.webhook_url}{method}.json"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=params or {}) as response:
                data = await response.json(content_type=None)

        if "error" in data:
            error = data.get("error")
            description = data.get("error_description", "Без описания")
            raise BitrixError(f"{error}: {description}")

        return data

    async def create_contact(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        comment: str | None = None,
    ) -> int:
        """
        Создаем контакт в Bitrix24.

        PHONE и EMAIL передаются как мультиполя.
        Это специальный формат Bitrix24 для телефонов и почты.
        """
        fields = {
            "NAME": name,
            "OPENED": "Y",
        }

        if phone:
            fields["PHONE"] = [
                {
                    "VALUE": phone,
                    "VALUE_TYPE": "WORK",
                }
            ]

        if email:
            fields["EMAIL"] = [
                {
                    "VALUE": email,
                    "VALUE_TYPE": "WORK",
                }
            ]

        if comment:
            fields["COMMENTS"] = comment

        result = await self.call(
            "crm.contact.add",
            {
                "fields": fields,
            },
        )

        return int(result["result"])

    async def create_deal(
        self,
        title: str,
        contact_id: int,
        service: str,
        budget: float | None,
        currency: str,
        category_id: int,
        comment: str | None = None,
    ) -> int:
        """
        Создаем сделку и сразу привязываем к ней контакт.
        """
        comments_parts = [
            f"Заявка из Telegram-бота",
            f"Услуга / запрос: {service}",
        ]

        if comment:
            comments_parts.append(f"Комментарий клиента: {comment}")

        fields = {
            "TITLE": title,
            "CATEGORY_ID": category_id,
            "CONTACT_IDS": [contact_id],
            "COMMENTS": "\n".join(comments_parts),
            "SOURCE_DESCRIPTION": "Telegram bot",
            "OPENED": "Y",
        }

        if budget is not None:
            fields["OPPORTUNITY"] = budget
            fields["CURRENCY_ID"] = currency
            fields["IS_MANUAL_OPPORTUNITY"] = "Y"

        result = await self.call(
            "crm.deal.add",
            {
                "fields": fields,
            },
        )

        return int(result["result"])
