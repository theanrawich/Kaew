import test from 'node:test';
import assert from 'node:assert/strict';
import {createVoiceBridge} from './voice-bridge.mjs';

test('voice commands pass through UART tank and controller interlocks',()=>{
  const bridge=createVoiceBridge();
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,false);
  bridge.placeCup();
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,false);
  bridge.observeLevel('wet');
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,true);
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,false);
  assert.equal(bridge.command({type:'stop'}).accepted,true);
  assert.equal(bridge.status().pump,false);
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,false);
});

test('malformed and stale or dry commands never start the pump',()=>{
  const bridge=createVoiceBridge(); bridge.placeCup(); bridge.observeLevel('wet');
  assert.equal(bridge.command({type:'refill',targetMl:NaN}).accepted,false);
  bridge.advance(6);
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,false);
  bridge.observeLevel('dry');
  assert.equal(bridge.command({type:'refill',targetMl:150}).accepted,false);
  assert.equal(bridge.status().pump,false);
});
