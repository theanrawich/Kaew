"""Reproducible ASR evaluation; generated audio must not be treated as human speech."""
import argparse
import json
import re
import time
import unicodedata
from pathlib import Path
from audio_service import FasterWhisperASR, TransformersThaiASR, _thai_number
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
    wake_cases=wake_hits=nonwake_cases=false_activations=0
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
        expected_wake=case['intent']!='no_wake'; detected_wake=prediction.startswith('แก้ว')
        if expected_wake:
            wake_cases+=1; wake_hits+=int(detected_wake)
        else:
            nonwake_cases+=1; false_activations+=int(detected_wake)
        chars+=len(rc); words+=len(rw); char_errors+=ce; word_errors+=we; correct+=int(intent==case['intent'])
        results.append({'reference':reference,'prediction':prediction,'expected_intent':case['intent'],'intent':intent,'latency_s':round(latency,3)})
    if not cases or not chars or not words: raise ValueError('empty evaluation set')
    return {'cases':len(cases),'cer':char_errors/chars,'wer':word_errors/words,'intent_accuracy':correct/len(cases),
            'wake_recall':wake_hits/wake_cases if wake_cases else None,
            'false_activation_rate':false_activations/nonwake_cases if nonwake_cases else None,'results':results}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',required=True);parser.add_argument('--manifest',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--backend',choices=('faster-whisper','transformers'),default='faster-whisper')
    args=parser.parse_args(); from pythainlp.tokenize import word_tokenize
    manifest=Path(args.manifest); cases=json.loads(manifest.read_text(encoding='utf-8'))['cases']
    model=(FasterWhisperASR if args.backend=='faster-whisper' else TransformersThaiASR)(args.model)
    result=evaluate_cases(cases,lambda path:model.transcribe((manifest.parent/path).read_bytes()),lambda text:word_tokenize(text,engine='newmm'))
    result.update({'model':args.model,'corpus':json.loads(manifest.read_text(encoding='utf-8')).get('description','unspecified'), 'tokenizer':'PyThaiNLP newmm','warning':'Check corpus provenance before interpreting accuracy.'})
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False))


if __name__=='__main__':main()
