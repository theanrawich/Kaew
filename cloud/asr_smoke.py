"""Opt-in real local ASR smoke test against an isolated temporary backend.

This exercises real ASR and real command services; TTS is an audible test tone,
not speech synthesis. No production data, credentials or hardware are used.
"""
import argparse
import io
import json
import math
import struct
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path
from audio_service import FasterWhisperASR, process_audio
from server import create_server


class ToneTTS:
    def synthesize(self,text):
        out=io.BytesIO()
        with wave.open(out,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
            w.writeframes(b''.join(struct.pack('<h',int(1500*math.sin(i/10))) for i in range(3200)))
        return out.getvalue()


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--model',required=True); parser.add_argument('--wav',required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        server=create_server('127.0.0.1',0,str(Path(directory)/'test.sqlite3'),'device-test','admin-test')
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            def command(text):
                request=urllib.request.Request('http://127.0.0.1:%d/api/voice'%server.server_port,
                    data=json.dumps({'text':text},ensure_ascii=False).encode(),method='POST',
                    headers={'Content-Type':'application/json','Authorization':'Bearer admin-test'})
                with urllib.request.urlopen(request,timeout=5) as response: return json.load(response)
            result=process_audio(Path(args.wav).read_bytes(),FasterWhisperASR(args.model),command,ToneTTS(),Path(directory)/'mock-tone.wav')
            print(json.dumps({'intent':result['intent'],'executed':result['executed'],'audio_written':result['audio_written'],'tts':'mock_tone'}))
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
