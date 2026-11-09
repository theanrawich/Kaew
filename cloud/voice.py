"""Thai text intent parsing; this module is not speech recognition or an AI model."""
import re
import unicodedata


def parse_text(text):
    if not isinstance(text,str) or not 0 < len(text) <= 500: return {'intent':'invalid'}
    text=unicodedata.normalize('NFC',text).strip().lower()
    if not text.startswith('แก้ว'): return {'intent':'no_wake'}
    text=text[4:].strip()
    if any(word in text for word in ('หยุด','stop','พอแล้ว')): return {'intent':'stop'}
    if any(word in text for word in ('สถานะอุปกรณ์','สถานะเครื่อง','device status')): return {'intent':'status'}
    if any(word in text for word in ('เตือน','remind','reminder')):
        if 'ครึ่งชั่วโมง' in text: minutes=30
        else:
            match=re.search(r'(\d+)\s*(นาที|ชั่วโมง|น\.|minutes?|mins?|hours?|hrs?)',text)
            if not match: return {'intent':'clarify_reminder'}
            minutes=int(match.group(1)); unit=match.group(2)
            if unit in ('ชั่วโมง','hour','hours','hr','hrs'): minutes*=60
        return {'intent':'reminder','minutes':minutes} if 1<=minutes<=1440 else {'intent':'invalid_reminder'}
    if any(word in text for word in ('เติม','ริน','refill','fill')) and any(word in text for word in ('น้ำ','water')):
        return {'intent':'refill'}
    if ('น้ำ' in text or 'water' in text) and any(word in text for word in ('เหลือ','ระดับ','ขวด','เท่าไหร่','level','left')):
        return {'intent':'level'}
    return {'intent':'unknown'}
