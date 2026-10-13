//! Experimental dense Mealy-product BFS. No dependencies, I/O, or Python callbacks.
use std::time::{Duration, Instant};

struct Outcome { status: i32, word: Vec<u32>, expanded: u32, discovered: u32 }
fn outcome(status: i32, word: Vec<u32>, expanded: u32, discovered: usize) -> Outcome {
    Outcome { status, word, expanded, discovered: discovered as u32 }
}

fn solve(nl: usize, nr: usize, k: usize, il: usize, ir: usize,
         lt: &[u32], lo: &[u32], rt: &[u32], ro: &[u32],
         max_pairs: usize, max_depth: u32, timeout_ms: u32, word_cap: usize) -> Outcome {
    if !(1..=1024).contains(&nl) || !(1..=1024).contains(&nr) || !(1..=64).contains(&k)
       || il >= nl || ir >= nr || lt.len() != nl*k || lo.len() != nl*k
       || rt.len() != nr*k || ro.len() != nr*k || max_pairs == 0 || max_pairs > 1_000_000
       || timeout_ms == 0 || timeout_ms > 60000 || word_cap == 0 || word_cap > 10000
       || lt.iter().any(|&x| x as usize >= nl) || rt.iter().any(|&x| x as usize >= nr) {
        return outcome(5, vec![], 0, 0);
    }
    let start = Instant::now();
    let deadline = Duration::from_millis(timeout_ms as u64);
    let root = il*nr+ir;
    let mut parents = vec![usize::MAX; nl*nr];
    let mut symbols = vec![0u32; nl*nr];
    parents[root] = root;
    let mut queue = Vec::with_capacity(max_pairs.min(nl*nr));
    queue.push((root,0u32));
    let mut cursor = 0;
    let mut expanded = 0;
    let mut cutoff = false;
    while cursor < queue.len() {
        if start.elapsed() >= deadline { return outcome(4,vec![],expanded,queue.len()); }
        let (pair,depth) = queue[cursor]; cursor += 1; expanded += 1;
        if depth >= max_depth { cutoff=true; continue; }
        let l=pair/nr; let r=pair%nr;
        for a in 0..k {
            if lo[l*k+a] != ro[r*k+a] {
                let mut word=vec![a as u32]; let mut p=pair;
                while p != root {
                    if word.len() >= word_cap { return outcome(6,vec![],expanded,queue.len()); }
                    word.push(symbols[p]); p=parents[p];
                }
                word.reverse(); return outcome(1,word,expanded,queue.len());
            }
            let next=lt[l*k+a] as usize*nr+rt[r*k+a] as usize;
            if parents[next] == usize::MAX {
                if queue.len() >= max_pairs { return outcome(2,vec![],expanded,queue.len()); }
                parents[next]=pair; symbols[next]=a as u32;
                queue.push((next,depth+1));
            }
        }
    }
    outcome(if cutoff {3} else {0},vec![],expanded,queue.len())
}

/// SAFETY: callers supply valid arrays of the stated lengths, a writable
/// word buffer of word_cap u32s, and a writable three-u32 stats buffer.
/// This ABI is called only by the trusted local binding, never by puzzle input.
#[no_mangle]
pub unsafe extern "C" fn polya_product(
    nl: u32, nr: u32, k: u32, il: u32, ir: u32,
    lt: *const u32, lo: *const u32, left_len: usize,
    rt: *const u32, ro: *const u32, right_len: usize,
    max_pairs: u32, max_depth: u32, timeout_ms: u32,
    word: *mut u32, word_cap: usize, stats: *mut u32) -> i32 {
    if lt.is_null() || lo.is_null() || rt.is_null() || ro.is_null() || word.is_null() || stats.is_null()
       || left_len > 65536 || right_len > 65536 { return 5; }
    let result=solve(nl as usize,nr as usize,k as usize,il as usize,ir as usize,
        std::slice::from_raw_parts(lt,left_len),std::slice::from_raw_parts(lo,left_len),
        std::slice::from_raw_parts(rt,right_len),std::slice::from_raw_parts(ro,right_len),
        max_pairs as usize,max_depth,timeout_ms,word_cap);
    *stats=result.expanded; *stats.add(1)=result.discovered; *stats.add(2)=result.word.len() as u32;
    if !result.word.is_empty() { std::ptr::copy_nonoverlapping(result.word.as_ptr(),word,result.word.len()); }
    result.status
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn equivalence() {
        assert_eq!(solve(1,1,1,0,0,&[0],&[3],&[0],&[3],10,100,1000,100).status,0);
    }
    #[test] fn delayed_witness() {
        let r=solve(2,2,1,0,0,&[1,1],&[0,1],&[1,1],&[0,2],10,100,1000,100);
        assert_eq!(r.status,1); assert_eq!(r.word,vec![0,0]);
    }
    #[test] fn budgets_and_bad_edges() {
        assert_eq!(solve(2,2,1,0,0,&[1,1],&[0,1],&[1,1],&[0,2],1,100,1000,100).status,2);
        assert_eq!(solve(1,1,1,0,0,&[0],&[0],&[0],&[0],10,0,1000,100).status,3);
        assert_eq!(solve(1,1,1,0,0,&[1],&[0],&[0],&[0],10,100,1000,100).status,5);
        assert_eq!(solve(2,2,1,0,0,&[1,1],&[0,1],&[1,1],&[0,2],10,100,1000,1).status,6);
    }
}
