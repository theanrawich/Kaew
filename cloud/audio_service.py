"""WAV input, local Faster-Whisper ASR and Google Cloud Thai TTS adapters."""
import base64
import binascii
import io
import json
import math
import re
import struct
import unicodedata
import urllib.request
import wave
from pathlib import Path
from notifications import NoRedirect


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


class FasterWhisperASR:
    def __init__(self, model_path=None, model=None):
        if model is None:
            if not model_path: raise AudioError('local Faster-Whisper model path required')
            try:
                from faster_whisper import WhisperModel
                model=WhisperModel(model_path,device='cpu',compute_type='int8',local_files_only=True)
            except Exception: raise AudioError('ASR model or runtime unavailable') from None
        self.model=model

    def transcribe(self,audio):
        validate_wav(audio)
        try:
            segments,_=self.model.transcribe(io.BytesIO(audio),language='th',vad_filter=True,beam_size=5,condition_on_previous_text=False)
            text=''.join(s.text for s in segments).strip()
        except Exception: raise AudioError('speech recognition failed') from None
        if not text or len(text)>500: raise AudioError('no usable speech recognized')
        return text


class TransformersThaiASR:
    """Local Thai-finetuned Whisper, with the same strict WAV boundary."""
    def __init__(self, model_path=None, engine=None):
        if engine is None:
            if not model_path: raise AudioError('local ASR model path required')
            try:
                import numpy as np
                import torch
                from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
                processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
                model=AutoModelForSpeechSeq2Seq.from_pretrained(model_path,local_files_only=True).eval()
                def engine(samples):
                    array=np.asarray(samples,dtype=np.float32)/32768.0
                    inputs=processor(array,sampling_rate=16000,return_tensors='pt')
                    with torch.inference_mode():
                        ids=model.generate(inputs.input_features,language='th',task='transcribe',max_new_tokens=180)
                    return processor.batch_decode(ids,skip_special_tokens=True)[0]
            except Exception: raise AudioError('Thai ASR model or runtime unavailable') from None
        self.engine=engine

    def transcribe(self,audio):
        validate_wav(audio)
        pcm=inspect_wav(audio,True)['pcm']
        try: text=self.engine([x[0] for x in struct.iter_unpack('<h',pcm)]).strip()
        except Exception: raise AudioError('Thai speech recognition failed') from None
        if not text or len(text)>500: raise AudioError('no usable speech recognized')
        return text


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


def _thai_number(n):
    if not 0<=n<=999999: raise AudioError('number out of range')
    if n==0: return 'ศูนย์'
    digits=('ศูนย์','หนึ่ง','สอง','สาม','สี่','ห้า','หก','เจ็ด','แปด','เก้า')
    places=('','สิบ','ร้อย','พัน','หมื่น','แสน'); out=''
    for position in range(5,-1,-1):
        digit=(n//(10**position))%10
        if not digit: continue
        if position==1: out+=('' if digit==1 else 'ยี่' if digit==2 else digits[digit])+'สิบ'
        elif position==0 and digit==1 and n>=10: out+='เอ็ด'
        else: out+=digits[digit]+places[position]
    return out


def normalize_thai_tts(text):
    if not isinstance(text,str) or not 0<len(text)<=300: raise AudioError('invalid TTS text')
    text=unicodedata.normalize('NFC',text)
    text=re.sub(r'\d+',lambda match:_thai_number(int(match.group())),text)
    text=re.sub(r'[.,!?\-:;()]+','',text)
    if any(not (ch.isspace() or '\u0e00'<=ch<='\u0e7f') for ch in text): raise AudioError('unsupported TTS characters')
    text=' '.join(text.split())
    if not text: raise AudioError('empty TTS text')
    return text


class MmsThaiTTS:
    """Local Meta MMS Thai VITS; model license is CC-BY-NC-4.0."""
    def __init__(self,model_path=None,engine=None):
        if engine is None:
            if not model_path: raise AudioError('local MMS model path required')
            try:
                import torch
                from transformers import VitsModel, AutoTokenizer
                model=VitsModel.from_pretrained(model_path,local_files_only=True).eval()
                tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
                def engine(text):
                    with torch.inference_mode(): output=model(**tokenizer(text,return_tensors='pt')).waveform
                    return model.config.sampling_rate,output.squeeze().cpu().tolist()
            except Exception: raise AudioError('MMS TTS model or runtime unavailable') from None
        self.engine=engine

    def synthesize(self,text):
        text=normalize_thai_tts(text)
        try:
            rate,samples=self.engine(text)
            if rate!=16000 or not 0<len(samples)<=rate*30: raise ValueError('invalid speech output')
            if any(not math.isfinite(x) for x in samples): raise ValueError('nonfinite audio')
            pcm=b''.join(struct.pack('<h',int(max(-1,min(1,x))*32767)) for x in samples)
            out=io.BytesIO()
            with wave.open(out,'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm)
            return out.getvalue()
        except Exception: raise AudioError('local Thai speech synthesis failed') from None


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
