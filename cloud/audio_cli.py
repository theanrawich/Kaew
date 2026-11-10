"""Explicit WAV → local ASR → authenticated Kaew API → Thai TTS WAV."""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from audio_service import AudioError, FasterWhisperASR, TransformersThaiASR, GoogleThaiTTS, MmsThaiTTS, process_audio
from notifications import NoRedirect


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input_wav'); parser.add_argument('output_wav')
    parser.add_argument('--model',required=True,help='local CTranslate2 Faster-Whisper model directory')
    parser.add_argument('--backend',choices=('faster-whisper','transformers'),default='faster-whisper')
    parser.add_argument('--tts-model',help='local MMS Thai TTS model directory')
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    args=parser.parse_args()
    url=urlsplit(args.url)
    if not url.hostname or (url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1'))):
        raise AudioError('backend requires HTTPS except loopback')
    admin=os.environ.get('KAEW_ADMIN_TOKEN',''); tts_token=os.environ.get('KAEW_GOOGLE_TTS_TOKEN','')
    if not admin or (not args.tts_model and not tts_token): raise AudioError('admin token and a TTS model or Google token are required')
    if Path(args.input_wav).resolve()==Path(args.output_wav).resolve(): raise AudioError('input and output must be distinct')
    def command(text):
        request=urllib.request.Request(args.url.rstrip('/')+'/api/voice',method='POST',
            headers={'Content-Type':'application/json','Authorization':'Bearer '+admin},
            data=json.dumps({'text':text},ensure_ascii=False).encode())
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=5) as response: return json.load(response)
        except Exception: raise AudioError('backend command failed') from None
    if Path(args.input_wav).stat().st_size>2_000_000: raise AudioError('input WAV too large')
    tts=MmsThaiTTS(args.tts_model) if args.tts_model else GoogleThaiTTS(tts_token)
    asr=(FasterWhisperASR if args.backend=='faster-whisper' else TransformersThaiASR)(args.model)
    result=process_audio(Path(args.input_wav).read_bytes(),asr,command,tts,args.output_wav)
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result.get('audio_written') else 2


if __name__=='__main__': sys.exit(main())
