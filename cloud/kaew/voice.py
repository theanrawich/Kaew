"""Thai text intent parsing; this module is not speech recognition or an AI model."""
import re
import unicodedata

THAI_DIGITS={'ศูนย์':0,'หนึ่ง':1,'สอง':2,'ยี่':2,'สาม':3,'สี่':4,'ห้า':5,'หก':6,'เจ็ด':7,'แปด':8,'เก้า':9,'เอ็ด':1}
THAI_NUMBER=r'(?:ศูนย์|หนึ่ง|สอง|ยี่|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|เอ็ด|สิบ|ร้อย|พัน)+'

def parse_thai_integer(text):
    tokens=re.findall(r'ศูนย์|หนึ่ง|สอง|ยี่|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|เอ็ด|สิบ|ร้อย|พัน',text)
    if ''.join(tokens)!=text: return None
    total=0; digit=None; last_scale=10000
    for token in tokens:
        if token in THAI_DIGITS:
            if digit is not None: return None
            digit=THAI_DIGITS[token]
        else:
            scale={'สิบ':10,'ร้อย':100,'พัน':1000}[token]
            if scale>=last_scale: return None
            last_scale=scale
            total+=(1 if digit is None else digit)*scale; digit=None
    return total+(digit or 0)


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
            if match: minutes=int(match.group(1)); unit=match.group(2)
            else:
                match=re.search('('+THAI_NUMBER+r')\s*(นาที|ชั่วโมง)',text)
                if not match: return {'intent':'clarify_reminder'}
                minutes=parse_thai_integer(match.group(1)); unit=match.group(2)
                if minutes is None: return {'intent':'clarify_reminder'}
            if unit in ('ชั่วโมง','hour','hours','hr','hrs'): minutes*=60
        return {'intent':'reminder','minutes':minutes} if 1<=minutes<=1440 else {'intent':'invalid_reminder'}
    if any(word in text for word in ('เติม','ริน','refill','fill')) and any(word in text for word in ('น้ำ','water')):
        return {'intent':'refill'}
    if ('น้ำ' in text or 'water' in text) and any(word in text for word in ('เหลือ','ระดับ','ขวด','เท่าไหร่','level','left')):
        return {'intent':'level'}
    return {'intent':'unknown'}
