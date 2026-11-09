// Local simulation only. The binary UART frame is decoded before HTTP ingestion.
import {randomInt} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {encodeFrame, createWireReceiver} from '../simulation/wire-codec.mjs';

const token = process.env.KAEW_DEVICE_TOKEN;
if (!token) throw new Error('KAEW_DEVICE_TOKEN is required');
const simulatedLevel = process.env.KAEW_SIM_LEVEL === 'dry' ? 2 : 1;
const frame = encodeFrame({node:1,session:randomInt(1, 0x100000000),seq:0,centiC:2500,adc:1234,level:simulatedLevel});
const receiver = createWireReceiver();
if (receiver.receive(frame, 0).status !== 'accepted') throw new Error('invalid UART frame');
const sample = receiver.snapshot();
const body = JSON.stringify({device_id:'node-1',session:sample.session,seq:sample.seq,
  level:['unknown','wet','dry'][sample.level],temperature_c:sample.centiC === -32768 ? null : sample.centiC/100,tds_adc:sample.adc,source:'simulated'});
const adapter = new URL('./gateway_push.py', import.meta.url);
const run = spawnSync(process.env.KAEW_PYTHON || 'python', [fileURLToPath(adapter)], {input:body,encoding:'utf8',env:process.env});
if (run.error) throw run.error;
process.stdout.write(run.stdout); process.stderr.write(run.stderr);
if (run.status !== 0) process.exit(run.status ?? 1);
