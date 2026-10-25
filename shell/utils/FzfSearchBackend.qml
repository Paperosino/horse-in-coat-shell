import QtQuick
import "scripts/fzf.js" as Fzf
QtObject {
 property var owner:null
 readonly property var finder: owner ? new Fzf.Finder(owner.list,Object.assign({selector:item=>owner.selector(item)},owner.extraOpts)) : null
 function query(search:string):var {
  return finder ? finder.find(search).sort((a,b)=>a.score===b.score?owner.selector(a.item).trim().length-owner.selector(b.item).trim().length:b.score-a.score).map(r=>r.item) : [];
 }
}
