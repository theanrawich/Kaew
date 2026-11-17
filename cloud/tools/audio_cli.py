"""Explicit WAV → Groq Whisper → authenticated Kaew API → Thai TTS WAV."""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

# Support direct execution from any working directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from urllib.parse import urlsplit
from kaew.audio_service import AudioError, GroqWhisperASR, GoogleThaiTTS, process_audio
from kaew.notifications import NoRedirect


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input_wav'); parser.add_argument('output_wav')
    parser.add_argument('--model', default='whisper-large-v3-turbo', help='Groq Whisper model id')
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    args=parser.parse_args()
    url=urlsplit(args.url)
    if not url.hostname or (url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1'))):
        raise AudioError('backend requires HTTPS except loopback')
    admin=os.environ.get('KAEW_ADMIN_TOKEN',''); tts_token=os.environ.get('KAEW_GOOGLE_TTS_TOKEN','')
    if not admin or not tts_token: raise AudioError('admin token and Google TTS token are required')
    if Path(args.input_wav).resolve()==Path(args.output_wav).resolve(): raise AudioError('input and output must be distinct')
    def command(text):
        request=urllib.request.Request(args.url.rstrip('/')+'/api/voice',method='POST',
            headers={'Content-Type':'application/json','Authorization':'Bearer '+admin},
            data=json.dumps({'text':text},ensure_ascii=False).encode())
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=5) as response: return json.load(response)
        except Exception: raise AudioError('backend command failed') from None
    if Path(args.input_wav).stat().st_size>2_000_000: raise AudioError('input WAV too large')
    tts=GoogleThaiTTS(tts_token)
    asr=GroqWhisperASR(os.environ.get('GROQ_API_KEY',''),model=args.model)
    result=process_audio(Path(args.input_wav).read_bytes(),asr,command,tts,args.output_wav)
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result.get('audio_written') else 2


if __name__=='__main__': sys.exit(main())
