// Simulation-only typed command adapter. No GPIO, network or physical actuation.
import {createWireSimulation} from './wire-simulation.mjs';
import {encodeFrame} from './wire-codec.mjs';

export function createVoiceBridge() {
  const sim=createWireSimulation(), plant=sim.plant;
  let seq=0;
  return {
    placeCup() {plant.placeCup();},
    observeLevel(level) {
      const value={unknown:0,wet:1,dry:2}[level];
      if (value===undefined) throw new TypeError('invalid level');
      return sim.receive(encodeFrame({node:1,session:1,seq:++seq,centiC:2500,adc:1000,level:value}));
    },
    advance(seconds) {sim.step(seconds);},
    status() {const s=plant.state; return {pump:s.pump,cupPresent:s.cupPresent,cupMl:s.cupMl,fault:s.fault,tankPermitted:s.tankPermitted};},
    command(command) {
      if (!command || typeof command!=='object') return {accepted:false};
      if (command.type==='stop' && Object.keys(command).length===1) {
        plant.pressStop(); return {accepted:true};
      }
      if (command.type==='refill' && Object.keys(command).length===2 && Number.isFinite(command.targetMl)) {
        return {accepted:sim.start(command.targetMl)};
      }
      return {accepted:false};
    }
  };
}
