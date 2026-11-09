import test from 'node:test';
import assert from 'node:assert/strict';
import {createWireSimulation} from './wire-simulation.mjs';
import {encodeFrame} from './wire-codec.mjs';
test('encoded node sample permits refill, while duplicates and stale link stop it', () => {
  const s=createWireSimulation(); s.plant.placeCup();
  assert.equal(s.start(100),false);
  const packet={node:1,session:7,seq:1,centiC:2500,adc:1000,level:1};
  const frame=encodeFrame(packet);
  assert.equal(s.receive(frame).status,'accepted'); assert.equal(s.start(100),true);
  s.step(4); assert.equal(s.receive(frame).status,'duplicate');
  s.step(1); assert.equal(s.plant.state.pump,false); assert.equal(s.plant.state.fault,'tank sensor unavailable');
  assert.equal(s.start(100),false);
});
