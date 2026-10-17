"""Offline checks for original development fixtures; not a held-out evaluation."""
from itertools import permutations, product
from collections import Counter
from pathlib import Path
import json
rows=list(permutations(range(1,5)))
solutions=[]
for g in product(rows,repeat=4):
 if any(len({g[r][c] for r in range(4)})!=4 for c in range(4)): continue
 if any(len({g[r][c] for r in range(br,br+2) for c in range(bc,bc+2)})!=4 for br in (0,2) for bc in (0,2)): continue
 solutions.append(sum(g,()))
def count(text):
 givens=tuple(map(int,text.replace('/','')))
 return sum(all(not a or a==b for a,b in zip(givens,s)) for s in solutions)
assert len(solutions)==288
assert count('0000/3412/2143/4321')==1
assert count('0000/3312/2143/4321')==0
assert count('0034/3412/0043/4321')==2
assert count('1034/3412/0043/4321')==1
print('PASS constraint fixture: 1 solution; duplicate control: 0')
print('PASS construction fixture: 2 solutions before restored clue; 1 after')
def tile(cells):
 if not cells: return 1
 a=min(cells)
 total=0
 for dr,dc in ((0,1),(0,-1),(1,0),(-1,0)):
  b=(a[0]+dr,a[1]+dc)
  if b in cells: total+=tile(cells-{a,b})
 return total
cells={(r,c) for r in range(4) for c in range(4)}-{(0,0),(3,3)}
assert Counter((r+c)%2 for r,c in cells)=={0:6,1:8}
for r,c in cells:
 for dr,dc in ((0,1),(1,0)):
  if (r+dr,c+dc) in cells: assert (r+c)%2 != (r+c+dr+dc)%2
assert tile(cells)==0
control={(0,0),(0,3)}
assert len({(r+c)%2 for r,c in control})==2 and tile(control)==0
print('PASS invariant fixture: 6/8 imbalance, 0 tilings; balanced control also has 0')
def prime(n): return n>1 and all(n%d for d in range(2,int(n**0.5)+1))
assert all(prime(n*n+n+11) for n in range(10))
assert 10*10+10+11==11*11 and not prime(121)
print('PASS counterexample fixture: 10 initial primes, then 121=11*11')
rectangles=[(0,3,0,3),(0,3,3,8),(3,8,0,3),(3,8,3,8)]
cover=Counter((x,y) for a,b,c,d in rectangles for x in range(a,b) for y in range(c,d))
assert len(cover)==64 and set(cover.values())=={1}
assert [(b-a)*(d-c) for a,b,c,d in rectangles]==[9,15,15,25]
print('PASS area fixture: 64 cells covered exactly once')
def edge(a,b): return ''.join(sorted((a,b)))
def trail_exists(edges):
 def rec(v,left):
  if not left: return True
  return any(rec(e[1] if e[0]==v else e[0],left-{e}) for e in left if v in e)
 return any(rec(v,set(edges)) for v in 'ABCD')
edges={'AB','BC','CD','AD','AC'}
route='ABCDAC'
assert Counter(edge(a,b) for a,b in zip(route,route[1:]))==Counter(edges)
assert trail_exists(edges) and not trail_exists(edges|{'BD'})
print('PASS graph fixture: witness valid; extra diagonal eliminates all edge-once trails')
cases=json.loads((Path(__file__).resolve().parents[1]/'polya/methods/data/examples.json').read_text())
assert len(cases)==6 and len({c['id'] for c in cases})==6
for c in cases:
 assert set(c)=={'id','methods','source','documented_evidence','reconstruction','toy_adaptation','applicability','limits','falsifiable_test'}
 assert set(c['source'])=={'url','author','title','license_basis'}
 assert set(c['toy_adaptation'])=={'provenance','problem','solution','verification'}
print('PASS collection schema: 6 uniquely identified cases')
