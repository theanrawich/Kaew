import base64
import io
import json
import audio_service
import urllib.error
from unittest.mock import patch, MagicMock
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from audio_service import validate_wav, FasterWhisperASR, TransformersThaiASR, GoogleThaiTTS, AudioError, process_audio, normalize_thai_tts, MmsThaiTTS


def wav_fixture(silent=False):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b''.join(struct.pack('<h',0 if silent else int(2500*math.sin(n/10))) for n in range(8000)))
    return out.getvalue()


class AudioTest(unittest.TestCase):
    def test_groq_multipart_and_validation(self):
        calls=[]
        def transport(url,headers,body):
            calls.append((url,headers,body))
            return json.dumps({'text':' สวัสดี '}).encode()
        asr=audio_service.GroqWhisperASR('test-placeholder',transport=transport)
        self.assertEqual(asr.transcribe(wav_fixture()),'สวัสดี')
        url,headers,body=calls[0]
        self.assertEqual(url,'https://api.groq.com/openai/v1/audio/transcriptions')
        self.assertEqual(headers['Authorization'],'Bearer test-placeholder')
        for part in (b'name="model"',b'whisper-large-v3-turbo',b'name="language"',b'\r\nth\r\n',
                     b'filename="audio.wav"',b'audio/wav',wav_fixture(),b'name="temperature"',b'name="response_format"'):
            self.assertIn(part,body)
        with self.assertRaises(AudioError): asr.transcribe(wav_fixture(True))
        self.assertEqual(len(calls),1)

    def test_groq_http_transport_is_bounded_and_disallows_redirects(self):
        response=MagicMock()
        response.__enter__.return_value=response
        response.read.return_value=b'{"text":"hello"}'
        opener=MagicMock()
        opener.open.return_value=response
        with patch('audio_service.urllib.request.build_opener',return_value=opener) as build:
            self.assertEqual(audio_service.GroqWhisperASR('test-placeholder').transcribe(wav_fixture()),'hello')
            self.assertIsInstance(build.call_args.args[0],audio_service.NoRedirect)
            self.assertEqual(opener.open.call_args.kwargs['timeout'],15)
            response.read.assert_called_once_with(65_537)
        for error in (urllib.error.HTTPError('https://api.groq.com',401,'denied',{},None),
                      urllib.error.URLError('offline'),TimeoutError()):
            with patch('audio_service.urllib.request.build_opener',return_value=opener):
                opener.open.side_effect=error
                with self.assertRaisesRegex(AudioError,'^speech recognition failed$'):
                    audio_service.GroqWhisperASR('test-placeholder').transcribe(wav_fixture())

    def test_groq_bad_responses_and_network_errors(self):
        for raw in (b'{}',b'not json',b'{"text":null}',b'{"text":" "}',json.dumps({'text':'a'*501}).encode(),b'x'*65537):
            with self.subTest(raw_size=len(raw)), self.assertRaises(AudioError):
                audio_service.GroqWhisperASR('test-placeholder',transport=lambda *a:raw).transcribe(wav_fixture())
        def broken(*args): raise OSError('private provider details')
        with self.assertRaisesRegex(AudioError,'^speech recognition failed$'):
            audio_service.GroqWhisperASR('test-placeholder',transport=broken).transcribe(wav_fixture())

    def test_wav_is_bounded_and_silence_rejected(self):
        self.assertEqual(validate_wav(wav_fixture())['sample_rate'],16000)
        with self.assertRaises(AudioError): validate_wav(wav_fixture(True))
        with self.assertRaises(AudioError): validate_wav(b'not wav')

    def test_whisper_adapter_uses_actual_wav_and_rejects_empty_recognition(self):
        class Model:
            def transcribe(self, audio, **opts):
                self.seen=audio.read(4); return iter([SimpleNamespace(text='แก้ว เติมน้ำให้หน่อย')]), None
        model=Model(); asr=FasterWhisperASR(model=model)
        self.assertEqual(asr.transcribe(wav_fixture()),'แก้ว เติมน้ำให้หน่อย'); self.assertEqual(model.seen,b'RIFF')
        class Empty:
            def transcribe(self,*a,**k): return iter([]),None
        with self.assertRaises(AudioError): FasterWhisperASR(model=Empty()).transcribe(wav_fixture())

    def test_tts_adapter_returns_playable_wav_and_validates_provider_data(self):
        def transport(payload, token): return {'audioContent':base64.b64encode(wav_fixture()).decode()}
        tts=GoogleThaiTTS('test-token',transport=transport)
        self.assertTrue(tts.synthesize('สวัสดี').startswith(b'RIFF'))
        with self.assertRaises(AudioError): GoogleThaiTTS('x',transport=lambda a,b:{'audioContent':'invalid'}).synthesize('test')

    def test_audio_to_command_to_playable_response(self):
        class ASR:
            def transcribe(self, audio): return 'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ'
        class TTS:
            def synthesize(self, text): return wav_fixture()
        command=lambda text: {'intent':'reminder','executed':True,'reply':'ได้เลย'}
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'response.wav'
            result=process_audio(wav_fixture(),ASR(),command,TTS(),dest)
            self.assertEqual(result['intent'],'reminder')
            with wave.open(str(dest),'rb') as w: self.assertEqual(w.getframerate(),16000)

    def test_tts_failure_reports_command_was_already_executed(self):
        class ASR:
            def transcribe(self,audio): return 'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ'
        class BrokenTTS:
            def synthesize(self,text): raise OSError('offline')
        calls=[]
        def command(text): calls.append(text); return {'intent':'reminder','executed':True,'reply':'ได้เลย'}
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'response.wav'
            result=process_audio(wav_fixture(),ASR(),command,BrokenTTS(),dest)
            self.assertTrue(result['executed']); self.assertFalse(result['audio_written'])
            self.assertEqual(len(calls),1); self.assertFalse(dest.exists())

    def test_thai_numbers_and_mock_mms_pcm_make_esp_compatible_wav(self):
        self.assertEqual(normalize_thai_tts('อีก 30 นาที'),'อีก สามสิบ นาที')
        self.assertEqual(normalize_thai_tts('น้ำ 21 มล.'),'น้ำ ยี่สิบเอ็ด มล')
        tts=MmsThaiTTS(engine=lambda text: (16000,[0.1,-0.1]*200))
        audio=tts.synthesize('เตือนอีก 30 นาที')
        with wave.open(io.BytesIO(audio),'rb') as w:
            self.assertEqual((w.getframerate(),w.getnchannels(),w.getsampwidth()),(16000,1,2))
        with self.assertRaises(AudioError): tts.synthesize('')

    def test_transformers_asr_uses_validated_pcm(self):
        calls=[]
        asr=TransformersThaiASR(engine=lambda samples: calls.append(len(samples)) or 'แก้ว เติมน้ำให้หน่อย')
        self.assertEqual(asr.transcribe(wav_fixture()),'แก้ว เติมน้ำให้หน่อย')
        self.assertGreater(calls[0],0)
        with self.assertRaises(AudioError): asr.transcribe(wav_fixture(silent=True))


if __name__=='__main__': unittest.main()
