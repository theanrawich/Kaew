"""Advisory-only local-model hydration recommendations; never drives an actuator."""
import json
import math
import urllib.request
from notifications import NoRedirect


class InvalidInput(ValueError): pass


def _number(value, lo, hi, nullable=False):
    return (nullable and value is None) or (type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi)


def validate_context(c):
    if not isinstance(c,dict) or set(c)!={'goal_ml','drank_ml','minutes_since_drink','cup_ml','profile'}: raise InvalidInput('invalid context')
    if not (_number(c['goal_ml'],100,10000,True) and _number(c['drank_ml'],0,20000) and
            _number(c['minutes_since_drink'],0,10080,True) and _number(c['cup_ml'],0,300,True) and
            c['profile'] in ('balanced','gentle','active')): raise InvalidInput('invalid context values')


def fallback():
    return {'source':'fallback','refill_ml':0,'reminder_minutes':60,'confidence':None,'actuation_allowed':False,
            'explanation':'ค่าเริ่มต้นชั่วคราว ไม่ใช่คำแนะนำทางการแพทย์'}


def recommend(context,provider):
    validate_context(context)
    try:
        result=provider(context) if provider else None
        if not isinstance(result,dict) or set(result)!={'refill_ml','reminder_minutes','confidence','explanation'}: return fallback()
        if not (_number(result['refill_ml'],0,250) and _number(result['reminder_minutes'],15,240) and
                _number(result['confidence'],0.5,1) and isinstance(result['explanation'],str) and 0<len(result['explanation'])<=300): return fallback()
        # A model's self-reported confidence is not a calibrated probability.
        bounded=dict(result)
        # Provisional 250 mL limit only bounds an advisory; unknown cup forbids a volume proposal.
        bounded['refill_ml']=min(result['refill_ml'],max(0,250-context['cup_ml'])) if context['cup_ml'] is not None else 0
        return {'source':'model',**bounded,'actuation_allowed':False}
    except Exception:
        return fallback()


class OllamaProvider:
    """Ollama must already run on loopback and have a suitable local model installed."""
    def __init__(self,model,port=11434):
        if not isinstance(model,str) or not model or len(model)>120 or not 1<=port<=65535: raise ValueError('invalid model configuration')
        self.model,self.url=model,'http://127.0.0.1:%d/api/generate'%port

    def __call__(self,context):
        prompt=('Return JSON only with refill_ml (0..250), reminder_minutes (15..240), confidence (0..1), '
                'explanation (short). This is a nonmedical hydration reminder. Use null inputs as unknown. Data: '+json.dumps(context,ensure_ascii=False))
        body=json.dumps({'model':self.model,'prompt':prompt,'format':'json','stream':False,'options':{'temperature':0}}).encode()
        request=urllib.request.Request(self.url,data=body,method='POST',headers={'Content-Type':'application/json'})
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
            raw=response.read(16385)
            if len(raw)>16384: raise ValueError('model response too large')
            outer=json.loads(raw)
        if outer.get('done') is not True: raise ValueError('incomplete model response')
        return json.loads(outer['response'])
