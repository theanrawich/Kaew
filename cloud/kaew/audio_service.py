"""WAV input, Typhoon hosted ASR, and Edge Thai TTS adapters."""
import asyncio
from contextlib import aclosing, closing
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


REMINDER_PHRASE = 'ถึงเวลาดื่มน้ำแล้ว'
RETRY_PHRASE = 'ขออภัย กรุณาพูดอีกครั้ง'
TTS_RATE = 16000
MAX_TTS_PCM_BYTES = 15 * TTS_RATE * 2
MAX_TTS_WAV_BYTES = 44 + MAX_TTS_PCM_BYTES
MAX_TTS_MP3_BYTES = 128 * 1024


async def edge_tts_request(text, voice):
    import edge_tts

    # The library requests only 24 kHz mono MP3. Bound the compressed input
    # before decoding and resampling with the miniaudio wheel.
    audio = bytearray()
    stream = edge_tts.Communicate(text, voice=voice).stream()
    async with aclosing(stream):
        async for chunk in stream:
            if chunk['type'] == 'audio':
                audio.extend(chunk['data'])
                if len(audio) > MAX_TTS_MP3_BYTES:
                    raise AudioError('TTS response too large')
    return bytes(audio)


def mp3_to_speech_wav(audio):
    import miniaudio

    if not isinstance(audio, bytes) or not 0 < len(audio) <= MAX_TTS_MP3_BYTES:
        raise AudioError('invalid TTS response')
    stream = miniaudio.stream_memory(audio, output_format=miniaudio.SampleFormat.SIGNED16,
                                     nchannels=1, sample_rate=TTS_RATE)
    pcm = bytearray()
    with closing(stream):
        for samples in stream:
            if sys.byteorder == 'big':
                samples.byteswap()
            pcm.extend(samples.tobytes())
            if len(pcm) > MAX_TTS_PCM_BYTES:
                raise AudioError('TTS speech too long')
    if not pcm:
        raise AudioError('TTS returned no samples')
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((1, 2, TTS_RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(pcm)
    return output.getvalue()


class EdgeTTS:
    voices = ('th-TH-NiwatNeural', 'th-TH-PremwadeeNeural')
    attempt_timeout = 4  # Up to 16 seconds of network time across all attempts.

    def __init__(self, transport=edge_tts_request):
        self.transport = transport

    def synthesize(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 500:
            raise AudioError('invalid TTS text')
        return asyncio.run(self._synthesize(text))

    async def _synthesize(self, text):
        for voice in self.voices:
            for _ in range(2):
                try:
                    audio = await asyncio.wait_for(self.transport(text, voice),
                                                   timeout=self.attempt_timeout)
                    return mp3_to_speech_wav(audio)
                except Exception as exc:
                    print('edge tts error:', voice, type(exc).__name__, file=sys.stderr)
        raise AudioError('Thai speech synthesis failed')


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
