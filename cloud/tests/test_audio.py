import base64
import io
import json
from kaew import audio_service
import urllib.error
from unittest.mock import patch, MagicMock
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from kaew.audio_service import validate_wav, GoogleThaiTTS, AudioError, process_audio


def wav_fixture(silent=False):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b''.join(struct.pack('<h',0 if silent else int(2500*math.sin(n/10))) for n in range(8000)))
    return out.getvalue()


class AudioTest(unittest.TestCase):
    def test_typhoon_sends_documented_model_and_original_wav(self):
        transport = MagicMock(return_value=json.dumps({'text': ' สวัสดี '}).encode())
        audio = wav_fixture()
        asr = audio_service.TyphoonASR('test-typhoon', transport=transport)
        self.assertEqual(asr.transcribe(audio), 'สวัสดี')
        url, headers, body = transport.call_args.args
        self.assertEqual(url, 'https://api.opentyphoon.ai/v1/audio/transcriptions')
        self.assertEqual(headers['Authorization'], 'Bearer test-typhoon')
        self.assertIn(b'name="model"\r\n\r\ntyphoon-asr-realtime\r\n', body)
        for part in (b'filename="audio.wav"', b'Content-Type: audio/wav', audio):
            self.assertIn(part, body)
        with self.assertRaises(AudioError):
            asr.transcribe(wav_fixture(True))
        transport.assert_called_once()
        self.assertNotIn(b'name="temperature"', body)

    def test_typhoon_http_transport_is_bounded_and_disallows_redirects(self):
        response=MagicMock()
        response.__enter__.return_value=response
        response.read.return_value=b'{"text":"hello"}'
        opener=MagicMock()
        opener.open.return_value=response
        with patch('kaew.audio_service.urllib.request.build_opener',return_value=opener) as build:
            self.assertEqual(audio_service.TyphoonASR('test-placeholder').transcribe(wav_fixture()),'hello')
            self.assertIsInstance(build.call_args.args[0],audio_service.NoRedirect)
            self.assertEqual(opener.open.call_args.kwargs['timeout'],15)
            response.read.assert_called_once_with(65_537)
        for error in (urllib.error.HTTPError('https://api.opentyphoon.ai',401,'denied',{},None),
                      urllib.error.URLError('offline'),TimeoutError()):
            with patch('kaew.audio_service.urllib.request.build_opener',return_value=opener):
                opener.open.side_effect=error
                with self.assertRaisesRegex(AudioError,'^speech recognition failed$'):
                    audio_service.TyphoonASR('test-placeholder').transcribe(wav_fixture())

    def test_typhoon_bad_responses_and_network_errors(self):
        for raw in (b'{}',b'not json',b'{"text":null}',b'{"text":" "}',json.dumps({'text':'a'*501}).encode(),b'x'*65537):
            with self.subTest(raw_size=len(raw)), self.assertRaises(AudioError):
                audio_service.TyphoonASR('test-placeholder',transport=lambda *a:raw).transcribe(wav_fixture())
        def broken(*args): raise OSError('private provider details')
        with self.assertRaisesRegex(AudioError,'^speech recognition failed$'):
            audio_service.TyphoonASR('test-placeholder',transport=broken).transcribe(wav_fixture())

    def test_wav_is_bounded_and_silence_rejected(self):
        self.assertEqual(validate_wav(wav_fixture())['sample_rate'],16000)
        with self.assertRaises(AudioError): validate_wav(wav_fixture(True))
        with self.assertRaises(AudioError): validate_wav(b'not wav')

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


if __name__=='__main__': unittest.main()
