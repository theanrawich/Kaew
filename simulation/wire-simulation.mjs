import {createSimulation} from './controller.mjs';
import {createWireReceiver} from './wire-codec.mjs';

// Browser plant: tank state enters exclusively through the encoded UART v1 receiver.
// Plant flow and thresholds remain assumptions, not hardware results.
export function createWireSimulation(options) {
  const plant=createSimulation(options), receiver=createWireReceiver();
  const now = () => Math.floor(plant.state.time*1000)>>>0;
  const refresh = () => {const p=receiver.snapshot(); plant.setTankPermitted(receiver.fresh(now()) && p.level===1);};
  refresh();
  return {plant, receive(frame) {const result=receiver.receive(frame,now()); refresh(); return result;},
    start(target) {refresh(); return plant.start(target);},
    step(dt) {
      if (!Number.isFinite(dt) || dt<0) throw new RangeError('invalid time');
      const snapshot=receiver.snapshot();
      const left=snapshot && receiver.fresh(now()) ? (5000-((now()-snapshot.receivedAt)>>>0))/1000 : 0;
      if (left>0 && dt>=left) {plant.step(left); refresh(); plant.step(dt-left);}
      else {plant.step(dt); refresh();}
    }
  };
}
