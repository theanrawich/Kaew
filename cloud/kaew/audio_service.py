"""WAV input, Typhoon hosted ASR, and Google Thai TTS adapters."""
import base64
import binascii
import io
import json
import math
import struct
import sys
import secrets
import urllib.request
import wave
from pathlib import Path
from kaew.notifications import NoRedirect


class AudioError(Exception): pass


def inspect_wav(audio, input_audio=False):
    if not isinstance(audio,bytes) or len(audio)>2_000_000: raise AudioError('invalid audio size')
    try:
        with wave.open(io.BytesIO(audio),'rb') as w:
            channels, width, rate, count = w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
            if width!=2 or channels not in (1,2) or not 8000<=rate<=48000 or w.getcomptype()!='NONE' or not 0<count<=rate*30:
                raise AudioError('unsupported WAV format')
            if input_audio and (channels!=1 or rate!=16000 or count>rate*15): raise AudioError('input must be mono 16-bit 16 kHz and at most 15 seconds')
            raw=w.readframes(count)
            if len(raw)!=count*channels*width: raise AudioError('truncated WAV')
            return {'sample_rate':rate,'channels':channels,'frames':count,'pcm':raw}
    except (wave.Error, EOFError, ValueError) as e: raise AudioError('invalid WAV') from e


def validate_wav(audio):
    info=inspect_wav(audio,True)
    values=struct.iter_unpack('<h',info.pop('pcm'))
    energy=sum(x[0]*x[0] for x in values)/info['frames']
    if math.sqrt(energy)<100: raise AudioError('silence or input too quiet')
    return info


def hosted_stt_request(url,headers,body):
    request=urllib.request.Request(url,data=body,headers=headers,method='POST')
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
        return response.read(65_537)


TYPHOON_ASR_MODEL = 'typhoon-asr-realtime'


class TyphoonASR:
    url = 'https://api.opentyphoon.ai/v1/audio/transcriptions'

    def __init__(self, api_key, transport=None):
        if not isinstance(api_key,str) or not api_key.strip() or any(ord(c)<33 or ord(c)>126 for c in api_key):
            raise AudioError('invalid ASR credentials')
        self.api_key = api_key
        self.model = TYPHOON_ASR_MODEL
        self.transport = transport or hosted_stt_request

    def transcribe(self,audio: bytes)->str:
        validate_wav(audio)
        boundary='kaew-'+secrets.token_hex(24)
        while boundary.encode() in audio: boundary='kaew-'+secrets.token_hex(24)
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{self.model}\r\n'.encode()
        ]
        parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()+audio+b'\r\n')
        parts.append(('--'+boundary+'--\r\n').encode())
        headers={'Authorization':'Bearer '+self.api_key,'Content-Type':'multipart/form-data; boundary='+boundary,'User-Agent':'KaewCloud/0.1'}
        try:
            raw=self.transport(self.url,headers,b''.join(parts))
            if not isinstance(raw,bytes) or len(raw)>65_536: raise ValueError()
            data=json.loads(raw)
            text=data.get('text') if isinstance(data,dict) else None
            if not isinstance(text,str): raise ValueError()
            text=text.strip()
            if not text or len(text)>500: raise ValueError()
            return text
        except Exception as exc:
            print('typhoon stt error:',type(exc).__name__,getattr(exc,'code',''),file=sys.stderr)
            raise AudioError('speech recognition failed') from None


def google_tts_request(payload,token):
    request=urllib.request.Request('https://texttospeech.googleapis.com/v1/text:synthesize',data=json.dumps(payload).encode(),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
        raw=response.read(3_000_001)
        if len(raw)>3_000_000: raise AudioError('TTS response too large')
        return json.loads(raw)


class GoogleThaiTTS:
    def __init__(self,token,voice='th-TH-Standard-A',transport=google_tts_request):
        if not token or not voice.startswith('th-TH-'): raise AudioError('TTS credentials or Thai voice missing')
        self.token,self.voice,self.transport=token,voice,transport

    def synthesize(self,text):
        if not isinstance(text,str) or not 0<len(text)<=500: raise AudioError('invalid TTS text')
        payload={'input':{'text':text},'voice':{'languageCode':'th-TH','name':self.voice},'audioConfig':{'audioEncoding':'LINEAR16','sampleRateHertz':16000}}
        try:
            data=self.transport(payload,self.token)
            audio=base64.b64decode(data['audioContent'],validate=True)
            inspect_wav(audio)
            return audio
        except (Exception, binascii.Error): raise AudioError('Thai speech synthesis failed') from None


def process_audio(audio, asr, command, tts, output_path):
    validate_wav(audio)
    transcript=asr.transcribe(audio)
    response=command(transcript)
    if not isinstance(response,dict) or not isinstance(response.get('reply'),str): raise AudioError('invalid command response')
    result={k:v for k,v in response.items() if k!='audio'}
    try:
        spoken=tts.synthesize(response['reply']); inspect_wav(spoken)
        Path(output_path).write_bytes(spoken)
        result['audio_written']=True
    except Exception:
        # The command may already have changed state. Never retry it implicitly.
        result['audio_written']=False; result['audio_error']='speech output failed after command processing'
    return result
