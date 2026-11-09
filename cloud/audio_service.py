"""WAV input, local Faster-Whisper ASR and Google Cloud Thai TTS adapters."""
import base64
import binascii
import io
import json
import math
import struct
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
