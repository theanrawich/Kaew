"""Reproducible ASR evaluation; generated audio must not be treated as human speech."""
import argparse
import json
import re
import time
import unicodedata
from pathlib import Path
from audio_service import FasterWhisperASR, _thai_number
from voice import parse_text


def edit_distance(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1): row.append(min(row[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=row
    return prev[-1]


def evaluate_cases(cases,recognize,tokenize):
    chars=words=char_errors=word_errors=correct=0; results=[]
    for case in cases:
        reference=unicodedata.normalize('NFC',case['text']).strip(); start=time.perf_counter()
        try: prediction=unicodedata.normalize('NFC',recognize(case['audio'])).strip()
        except Exception: prediction=''
        latency=time.perf_counter()-start
        def normalized(text):
            return re.sub(r'\d+',lambda m:_thai_number(int(m.group())) if int(m.group())<=999999 else m.group(),text)
        ref_norm, pred_norm=normalized(reference),normalized(prediction)
        rc=list(''.join(ref_norm.split())); pc=list(''.join(pred_norm.split()))
        rw=[t for t in tokenize(ref_norm) if t.strip()]; pw=[t for t in tokenize(pred_norm) if t.strip()]
        ce=edit_distance(rc,pc); we=edit_distance(rw,pw); intent=parse_text(prediction)['intent']
        chars+=len(rc); words+=len(rw); char_errors+=ce; word_errors+=we; correct+=int(intent==case['intent'])
        results.append({'reference':reference,'prediction':prediction,'expected_intent':case['intent'],'intent':intent,'latency_s':round(latency,3)})
    if not cases or not chars or not words: raise ValueError('empty evaluation set')
    return {'cases':len(cases),'cer':char_errors/chars,'wer':word_errors/words,'intent_accuracy':correct/len(cases),'results':results}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',required=True);parser.add_argument('--manifest',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(); from pythainlp.tokenize import word_tokenize
    manifest=Path(args.manifest); cases=json.loads(manifest.read_text(encoding='utf-8'))['cases']
    model=FasterWhisperASR(args.model)
    result=evaluate_cases(cases,lambda path:model.transcribe((manifest.parent/path).read_bytes()),lambda text:word_tokenize(text,engine='newmm'))
    result.update({'model':args.model,'corpus':'synthetic_single_voice','tokenizer':'PyThaiNLP newmm','warning':'Synthetic test only; not human-speech accuracy.'})
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False))


if __name__=='__main__':main()
