# Six source-backed mathematical method references

Read and assembled 2026-10-16. This is a small cited-reading method collection, not a downloaded book corpus or model-training dataset. Each record separates documented public evidence from newly written teaching material. No private expert reasoning is reconstructed or claimed.

## Files
- `examples.json`: strict agreed schema, six cases, original wording, source links and license caveats.
- `scripts/verify_method_examples.py` (repository root): original offline development checks. Run with Python 3; standard library only.

## Coverage
1. Norvig: finite-domain constraint propagation and branching; new 4-by-4 grid.
2. Norvig: generation is separate from certification; new ambiguous-grid/unique-grid pair. Our deletion construction is explicitly not his algorithm.
3. Mahajan: a coloring invariant rules out a tiling; new smaller board and a balanced-but-untileable control.
4. Rogers: target inputs that factor a polynomial; new coefficient-11 example.
5. Euclid/Joyce: partition a square to interpret an algebraic identity; new coordinate fixture.
6. Dudeney: odd-degree endpoints constrain drawing strokes; new graph and edge-adding rejection control.

## Rights and provenance
- Dudeney: Project Gutenberg catalogue explicitly says public domain **in the USA**. This does not establish status in every jurisdiction. No source illustrations included.
- Mahajan: the PDF copyright page explicitly licenses the book CC BY-NC-SA 4.0. These restrictions remain attached to its source record. No blanket commercial license is asserted for this collection or for source derivatives. Source expression reused elsewhere would require appropriate attribution and adherence to noncommercial/share-alike terms. No text or diagrams from the book are included here.
- Norvig, Rogers, and Joyce: publicly readable but a redistribution license was not verified. Included only as reading references with short independently written method descriptions. No source code, modern translation, images, or puzzle corpus copied.
- Toy fixtures and executable checks were written for this task. They illustrate mathematical ideas; their provenance does not imply permission to train on or redistribute the cited source books/pages.
- These fixtures are development material, not withheld tests. Successful execution validates the toy facts only; it does not establish improved general problem-solving ability.
- OpenStax was considered during discovery and excluded after its current preface stated restrictions on LLM ingestion/training. No OpenStax content is included in these records.

## Verification scope
The Sudoku verifier independently enumerates all 288 completed 4-by-4 grids, then counts completions for the selected givens. Tiling uses exhaustive exact-cover recursion. The graph test checks the explicit witness and exhaustively explores edge-once trails. Area coverage is checked cell by cell. The counterexample uses exact integer arithmetic. None of these checks calls a remote model, service, or paid API.
