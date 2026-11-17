"""Bounded reminder decisions. Suggested volume is advisory; no actuator interface."""
import json
import math
import os
import urllib.request
from types import SimpleNamespace
from kaew.notifications import NoRedirect

DEFAULT_MODEL = 'openai/gpt-oss-20b'
ADVICE_SCHEMA = {'type':'object', 'additionalProperties':False,
                'properties':{'next_reminder_minutes':{'type':'number'},
                              'suggested_ml':{'type':'number'}, 'reason':{'type':'string'}},
                'required':['next_reminder_minutes','suggested_ml','reason']}

class InvalidInput(ValueError): pass


def _number(value, lo, hi, nullable=False):
    return (nullable and value is None) or (type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi)


def validate_context(c):
    required={'goal_ml','drank_ml','minutes_since_drink','cup_ml','profile'}
    if not isinstance(c,dict) or not required <= set(c): raise InvalidInput('invalid context')
    if not (_number(c['goal_ml'],100,10000,True) and _number(c['drank_ml'],0,20000) and
            _number(c['minutes_since_drink'],0,10080,True) and _number(c['cup_ml'],0,300,True) and
            c['profile'] in ('balanced','gentle','active')): raise InvalidInput('invalid context values')


def parse_output(raw):
    if isinstance(raw,str):
        if len(raw)>4096: raise ValueError('model response too large')
        raw=raw.strip()
        if raw.startswith('```'):
            lines=raw.splitlines()
            if len(lines)<3 or lines[-1].strip()!='```': raise ValueError('invalid fence')
            raw='\n'.join(lines[1:-1])
        raw=json.loads(raw)
    return raw


def fallback(model=None):
    return {'source':'fallback','next_reminder_minutes':60,'suggested_ml':200,
            'reason':'Default reminder; model unavailable or invalid. Not medical advice.',
            'model':model,'fallback':True,'actuation_allowed':False}


def recommend(context,provider):
    validate_context(context)
    candidates=getattr(provider,'providers',(provider,))
    model=None
    for candidate in candidates:
        if candidate is None: continue
        model=getattr(candidate,'model',None)
        try:
            result=parse_output(candidate(context))
            if not isinstance(result,dict) or set(result)!=set(ADVICE_SCHEMA['required']): continue
            minutes,ml,reason=(result[k] for k in ('next_reminder_minutes','suggested_ml','reason'))
            if not (_number(minutes,-math.inf,math.inf) and _number(ml,-math.inf,math.inf) and
                    isinstance(reason,str) and 0<len(reason.strip())<=300): continue
            return {'source':'model','next_reminder_minutes':int(max(15,min(180,minutes))),
                    'suggested_ml':int(max(100,min(400,ml))),'reason':reason.strip(),
                    'model':model,'fallback':False,'actuation_allowed':False}
        except Exception:
            # Never surface transport exceptions: they can contain credentials.
            continue
    return fallback(model)


def prompt(context):
    return ('Choose the next non-medical hydration reminder from recent history. '
            'Return JSON only: {"next_reminder_minutes":15..180,"suggested_ml":100..400,"reason":"short reason"}. '
            'Volume is advisory only; never operate a pump. Null means unknown. Data: '
            +json.dumps(context,ensure_ascii=False,allow_nan=False))


class ChatProvider:
    """Small OpenAI-compatible HTTPS adapter; keys never enter logs or context."""
    def __init__(self,provider,key,model=DEFAULT_MODEL):
        self.model=model
        self.url={'groq':'https://api.groq.com/openai/v1/chat/completions',
                  'openrouter':'https://openrouter.ai/api/v1/chat/completions'}[provider]
        self._key=key

    def __call__(self,context):
        body=json.dumps({'model':self.model,'messages':[{'role':'user','content':prompt(context)}],
                         'response_format':{'type':'json_object'},'temperature':0,'max_tokens':512}).encode()
        request=urllib.request.Request(self.url,data=body,method='POST',headers={
            'Content-Type':'application/json','Authorization':'Bearer '+self._key,'User-Agent':'KaewCloud/0.1'})
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=9) as response:
            raw=response.read(16385)
        if len(raw)>16384: raise ValueError('model response too large')
        return parse_output(json.loads(raw)['choices'][0]['message']['content'])


def select_provider():
    model=os.environ.get('KAEW_AI_MODEL') or DEFAULT_MODEL
    providers=[]
    for name,env in (('groq','GROQ_API_KEY'),('openrouter','OPENROUTER_API_KEY')):
        key=os.environ.get(env)
        if key: providers.append(ChatProvider(name,key,model))
    if providers:
        return providers[0] if len(providers)==1 else SimpleNamespace(providers=providers)
    local=os.environ.get('KAEW_OLLAMA_MODEL')
    return OllamaProvider(local) if local else None


class OllamaProvider:
    def __init__(self,model,port=11434):
        if not isinstance(model,str) or not model or len(model)>120 or not 1<=port<=65535: raise ValueError('invalid model configuration')
        self.model,self.url=model,'http://127.0.0.1:%d/api/generate'%port

    def __call__(self,context):
        body=json.dumps({'model':self.model,'prompt':prompt(context),'format':ADVICE_SCHEMA,
                         'stream':False,'options':{'temperature':0}}).encode()
        request=urllib.request.Request(self.url,data=body,method='POST',headers={'Content-Type':'application/json','User-Agent':'KaewCloud/0.1'})
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=9) as response:
            raw=response.read(16385)
        if len(raw)>16384: raise ValueError('model response too large')
        outer=json.loads(raw)
        if outer.get('done') is not True: raise ValueError('incomplete model response')
        return parse_output(outer['response'])
