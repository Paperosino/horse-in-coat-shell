import QtQuick
import "scripts/fuzzysort.js" as Fuzzy
QtObject {
 property var owner:null
 readonly property var prepared: owner ? owner.list.map(e=>{const obj={_item:e};for(const k of owner.keys)obj[k]=Fuzzy.prepare(e[k]);return obj;}) : []
 function query(search:string):var {
  return owner ? Fuzzy.go(search,prepared,Object.assign({all:true,keys:owner.keys,scoreFn:r=>owner.weights.reduce((a,w,i)=>a+r[i].score*w,0)},owner.extraOpts)).map(r=>r.obj._item) : [];
 }
 Component.onDestruction:Fuzzy.cleanup()
}
