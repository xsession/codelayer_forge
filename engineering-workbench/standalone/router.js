function inflate(r,a){return{x:r.x-a,y:r.y-a,width:r.width+a*2,height:r.height+a*2}}
function inside(p,r){return p.x>r.x&&p.x<r.x+r.width&&p.y>r.y&&p.y<r.y+r.height}
function compress(points){if(points.length<=2)return points;const out=[points[0]];for(let i=1;i<points.length-1;i++){const a=out[out.length-1],b=points[i],c=points[i+1];if((a.y===b.y)!==(b.y===c.y))out.push(b)}out.push(points.at(-1));return out}
function segmentClear(a,b,obs){if(a.x!==b.x&&a.y!==b.y)return false;for(const r of obs){if(a.x===b.x){const y1=Math.min(a.y,b.y),y2=Math.max(a.y,b.y);if(a.x>r.x&&a.x<r.x+r.width&&y2>r.y&&y1<r.y+r.height)return false}else{const x1=Math.min(a.x,b.x),x2=Math.max(a.x,b.x);if(a.y>r.y&&a.y<r.y+r.height&&x2>r.x&&x1<r.x+r.width)return false}}return true}
class Heap{constructor(){this.a=[]}push(v){this.a.push(v);let i=this.a.length-1;while(i>0){const p=Math.floor((i-1)/2);if(this.a[p].score<=v.score)break;this.a[i]=this.a[p];i=p}this.a[i]=v}pop(){if(!this.a.length)return;const top=this.a[0],last=this.a.pop();if(this.a.length){let i=0;while(true){let c=i*2+1;if(c>=this.a.length)break;if(c+1<this.a.length&&this.a[c+1].score<this.a[c].score)c++;if(this.a[c].score>=last.score)break;this.a[i]=this.a[c];i=c}this.a[i]=last}return top}get size(){return this.a.length}}

export function routeOrthogonal(source,target,obstacles,options={}){
  const clearance=options.clearance??10,margin=options.margin??80,bendPenalty=options.bendPenalty??28;
  const obs=obstacles.map(r=>inflate(r,clearance)),xs=new Set([source.x,target.x,Math.min(source.x,target.x)-margin,Math.max(source.x,target.x)+margin]),ys=new Set([source.y,target.y,Math.min(source.y,target.y)-margin,Math.max(source.y,target.y)+margin]);
  for(const r of obs){xs.add(r.x);xs.add(r.x+r.width);ys.add(r.y);ys.add(r.y+r.height)}
  const xl=[...xs].sort((a,b)=>a-b),yl=[...ys].sort((a,b)=>a-b),pts=[],index=new Map(),pk=p=>`${p.x},${p.y}`;
  for(const y of yl)for(const x of xl){const p={x,y};if(obs.some(r=>inside(p,r))&&pk(p)!==pk(source)&&pk(p)!==pk(target))continue;index.set(pk(p),pts.length);pts.push(p)}
  const si=index.get(pk(source)),ti=index.get(pk(target));
  if(si===undefined||ti===undefined){const mx=(source.x+target.x)/2;return[source,{x:mx,y:source.y},{x:mx,y:target.y},target]}
  const graph=pts.map(()=>[]);
  for(const y of yl){const row=pts.map((p,i)=>({p,i})).filter(v=>v.p.y===y).sort((a,b)=>a.p.x-b.p.x);for(let j=0;j<row.length-1;j++){const a=row[j],b=row[j+1];if(segmentClear(a.p,b.p,obs)){const d=Math.abs(b.p.x-a.p.x);graph[a.i].push({to:b.i,d,dir:'H'});graph[b.i].push({to:a.i,d,dir:'H'})}}}
  for(const x of xl){const col=pts.map((p,i)=>({p,i})).filter(v=>v.p.x===x).sort((a,b)=>a.p.y-b.p.y);for(let j=0;j<col.length-1;j++){const a=col[j],b=col[j+1];if(segmentClear(a.p,b.p,obs)){const d=Math.abs(b.p.y-a.p.y);graph[a.i].push({to:b.i,d,dir:'V'});graph[b.i].push({to:a.i,d,dir:'V'})}}}
  const heap=new Heap(),sk=(i,d)=>`${i}:${d}`,start=sk(si,'X'),dist=new Map([[start,0]]),parent=new Map();heap.push({state:start,score:0});let final;
  while(heap.size){const cur=heap.pop();if(cur.score!==dist.get(cur.state))continue;const [it,dir]=cur.state.split(':'),i=Number(it);if(i===ti){final=cur.state;break}for(const e of graph[i]){const ns=sk(e.to,e.dir),score=cur.score+e.d+(dir!=='X'&&dir!==e.dir?bendPenalty:0);if(score<(dist.get(ns)??Infinity)){dist.set(ns,score);parent.set(ns,cur.state);heap.push({state:ns,score})}}}
  if(!final){const mx=(source.x+target.x)/2;return[source,{x:mx,y:source.y},{x:mx,y:target.y},target]}
  const route=[];let cur=final;while(cur){route.push(pts[Number(cur.split(':')[0])]);cur=parent.get(cur)}route.reverse();route[0]=source;route[route.length-1]=target;return compress(route)
}

export function routeIntersectsRect(points,rect){
  for(let i=0;i<points.length-1;i++){const a=points[i],b=points[i+1];if(a.x===b.x){const y1=Math.min(a.y,b.y),y2=Math.max(a.y,b.y);if(a.x>rect.x&&a.x<rect.x+rect.width&&y2>rect.y&&y1<rect.y+rect.height)return true}else if(a.y===b.y){const x1=Math.min(a.x,b.x),x2=Math.max(a.x,b.x);if(a.y>rect.y&&a.y<rect.y+rect.height&&x2>rect.x&&x1<rect.x+rect.width)return true}}return false
}
