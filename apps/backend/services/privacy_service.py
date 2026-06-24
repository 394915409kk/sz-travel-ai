PHONE_FIELDS = {"phone", "mobile", "customer_phone", "contact_phone"}
ID_FIELDS = {"document_number", "id_number", "passport_number", "passport_no"}
NAME_FIELDS = {"customer_name", "insured_customer_name"}


class PrivacyService:
    @staticmethod
    def mask_phone(value):
        if value is None:
            return None
        text = str(value)
        if len(text) < 7:
            return "*" * len(text)
        return f"{text[:3]}{'*' * max(len(text) - 7, 0)}{text[-4:]}"

    @staticmethod
    def mask_id_number(value):
        if value is None:
            return None
        text = str(value)
        if len(text) <= 7:
            return "*" * len(text)
        return f"{text[:3]}{'*' * (len(text) - 7)}{text[-4:]}"

    @staticmethod
    def mask_name(value):
        if value is None:
            return None
        text = str(value)
        if not text:
            return text
        return text[0] + "*" * max(len(text) - 1, 1)

    @classmethod
    def mask_sensitive_dict(cls, payload):
        if isinstance(payload, list):
            return [cls.mask_sensitive_dict(item) for item in payload]
        if not isinstance(payload, dict):
            return payload

        masked = {}
        for key, value in payload.items():
            if key in PHONE_FIELDS:
                masked[key] = cls.mask_phone(value)
            elif key in ID_FIELDS:
                masked[key] = cls.mask_id_number(value)
            elif key in NAME_FIELDS:
                masked[key] = cls.mask_name(value)
            else:
                masked[key] = cls.mask_sensitive_dict(value)
        return masked
