import json
from pathlib import Path
root=Path(__file__).resolve().parent
web_queries='''"dual feasible functions" "orthogonal packing" lower bounds Fekete Schepers
"energetic reasoning" "two-dimensional" packing
"set covering" "dual" "infeasibility" packing weights facility
"one-dimensional relaxations and LP bounds for orthogonal packing"
"non rectangular" "packing" "lower bounds" rectangles
"set covering" "surrogate relaxation" lower bounds Caprara
"A General Framework for Bounds" Fekete Schepers DOI
"A new constraint programming approach" Clautiaux Carlier Moukrim energetic reasoning DOI
"New reduction procedures and lower bounds" "two-dimensional" packing Carlier
"set covering" "Lagrangian" "lower bounds" Caprara Fischetti Toth 1999
"Using dual feasible functions to construct fast lower bounds for routing and location problems"
"geometric covering" "dual" "certificate" squares
"capacitated facility location" "lower bounds" Lagrangian relaxation
"A heuristic method for the set covering problem" Caprara Fischetti Toth DOI
"rectangle packing" "obstacles" "lower bound"
"facility layout" "lower bounding" procedures
"packing" "coloring invariants" polyomino
"orthogonal packing" "symmetry breaking" Fekete Schepers
"cumulative" "energetic reasoning" Baptiste Le Pape Nuijten 1999
"mandatory area" packing rectangles constraint
"non rectangular container" rectangle packing exact
"conservative scales in packing problems" Belov Scheithauer
"orthogonal packing" "interval graphs" Fekete Schepers combinatorial characterization
"Explanations for Energetic Reasoning" DOI
"rectangle packing" "L-shaped" "bound"
"bp_contrainte.pdf" Clautiaux
"A new constraint programming approach" filetype:pdf
"An L-approach" "upper bounds" Lins Morabito 2003
"rectangle packing" "wasted space" Korf lower bound
"Optimal Rectangle Packing" Huang Korf 2013
"rectangle packing" "Hall" constraint
"packing" "coloring" "linear programming" rectangles upper bound
"LP bounds in various constraint programming approaches for orthogonal packing"
"LP Bounds in an Interval-Graph Algorithm for Orthogonal-Packing Feasibility"
"New lower bounds for bin packing problems with conflicts"
"surrogate relaxation" "set covering" "lower bound" Lorena Lopes
"New filtering for the cumulative constraint" "non-overlapping rectangles"
"cumulative overload checking" energetic reasoning O(n log n)
"rectangle packing" "obstacles" "linear programming"
"A new constraint programming approach for the orthogonal packing problem" energetic area domains
"A new constraint programming approach for the orthogonal packing problem" hal
"One-dimensional relaxations and LP bounds" Belov pdf TU Dresden
"New reduction procedures and lower bounds" hal
"dual feasible functions" "energetic reasoning" cumulative scheduling
"surrogate relaxation" "set covering" Lorena Lopes 1994
"rectangle packing" "coloring invariants" weighted
"set covering" "Farkas" geometric certificate
"packing rectangles" "non-convex container" Forghani 2024
"polyomino" "tiling invariants" "linear" Conway Lagarias
"Analysis of upper bounds for the pallet loading problem"
"Analysis of upper bounds for the pallet loading problem" filetype:pdf Letchford
"A New Algorithm Based on Colouring Arguments" authors
"orthogonal packing" "Hall theorem" domains
"rectangle packing" "mandatory area" energetic
"The Two-Dimensional Finite Bin Packing Problem" "Part II" Boschetti Mingozzi
"New data-dependent dual-feasible functions and lower bounds" 2009
"Applications for Cutting and Packing Problems" "Alves" dual feasible
"Enhanced energetic reasoning-based lower bounds" DOI
"Consecutive Ones Matrices for Multi-dimensional Orthogonal Packing Problems" abstract
"A Dynamic Subgradient-Based Branch-and-Bound Procedure for Set Covering" abstract
"Optimal Solution of Set Covering/Partitioning Problems Using Dual Heuristics" abstract
"A survey of dual-feasible and superadditive functions" Clautiaux abstract
"Exact solution techniques for two-dimensional cutting and packing" arxiv
"New data-dependent dual-feasible functions and lower bounds" Carlier Moukrim
"New Filtering" "cumulative" "Beldiceanu" Poder Springer
"The minimum raster set" "orthogonal packing" abstract
"A Computational Study of Lower Bounds" "Two Dimensional" abstract
"A branch and bound algorithm for the strip packing problem" Alvarez Valdes lower bounds
"Optimal rectangle packing" "Moffitt" Pollack abstract
"A skyline heuristic for the 2D rectangular packing and strip packing problems" abstract
"A cutting-plane approach" "orthogonal non-guillotine" Baldacci Boschetti
"Bidimensional Packing by Bilinear Programming" Caprara Locatelli Monaci
"Orthogonal Packing Feasibility, Two-Dimensional Knapsack Problems" abstract
"A Computational Study of Lower Bounds for the Two Dimensional Bin Packing Problem" Serairi Haouari
"Integer programming based methods applied to cutting, packing, and scheduling" Lima 2021
"Lower bounds and reduction procedures for the bin packing problem" Martello Toth abstract
"Trimming Pseudo-Boolean Proofs" 2026 arxiv
"Solving the Pallet Loading Problem More Efficiently" Nelissen 1994
"A branch-and-cut algorithm for Mixed-Integer Bilinear Programming" abstract
"Basing Decisions on Sentences in Decision Diagrams" Darwiche Oztok
"Approximation algorithms for combinatorial problems" Johnson 1974 abstract
"An improved typology of cutting and packing problems" abstract
"Solving the Pallet Loading Problem More Efficiently" abstract Nelissen
"Classical Dual-Feasible Functions" "General Dual-Feasible Functions" Springer
"rectangle packing" "input output ports" "infeasibility"
"facility layout" "power coverage" "lower bound"
"rectangle packing" "holes" "infeasibility certificate"'''
agent_queries='''"certifying" "mixed integer" "VIPR" proof
"VeriPB" "pseudo-Boolean" proof logging paper
"constraint programming" "proof logging" packing paper
"Verifying integer programming results" Cheung Gleixner Steffy
"proof logging" "cumulative"
"proof logging" "non-overlap"
"Certifying Dominance and Symmetry Breaking" DOI
"Certifying Dominance and Symmetry Breaking"
"A Multi-Stage Proof Logging Framework to Certify the Correctness of CP Solvers"
"Proof Logging" "constraint programming" McCreesh 2022
"Practically Feasible Proof Logging" authors
"An Auditable Constraint Programming Solver" DOI
"Certified Dominance and Symmetry Breaking for Combinatorial Optimisation" DOI
"10.1007/bf01582278"
"10.1016/j.cor.2013.11.006"
"10.1007/978-0-387-35608-2_22"
"10.1007/978-3-319-42902-1_8"
"10.1016/j.ejor.2024.10.040"
"10.1016/j.ejor.2018.04.046"
"10.1007/s10479-014-1572-z"
"A new branch-and-cut approach for integrated planning in additive manufacturing" [domain:sciencedirect.com]
"The minimum raster set problem and its application" [domain:sciencedirect.com]
"A dual bounding scheme for a territory design problem" [domain:sciencedirect.com]'''
rows=[{'source':'web.run','query':q,'seat':'main'} for q in web_queries.splitlines()]
rows += [{'source':'web.run','query':q,'seat':'research background'} for q in agent_queries.splitlines()]
for q in ['dual feasible functions orthogonal packing','energetic reasoning orthogonal packing','set covering lower bound dual','two dimensional packing lower bounds']:
 rows.append({'source':'OpenAlex via lit.py','query':q,'phase':'initial quota'})
for q in ['Bidimensional packing by bilinear programming','proof logging dynamic programming decision diagrams','Analysis of upper bounds for the Pallet Loading Problem','Pseudo-Boolean Reasoning About States and Transitions']:
 rows.append({'source':'OpenAlex via lit.py','query':q,'phase':'keyed quota supplement'})
rows += [{'source':'arXiv via lit.py','query':'energetic reasoning'}, {'source':'arXiv via lit.py','query':'Bidimensional packing by bilinear programming','note':'First supplement attempt fell back due to local stale budget cache; 0 results; OpenAlex retry succeeded.'},{'source':'Crossref via lit.py','query':'non rectangular container packing bounds'}]
for q in ['title_t:"A new constraint programming approach for the orthogonal packing problem"','title_t:"New reduction procedures and lower bounds for the two-dimensional bin packing problem"','title_t:"One-dimensional relaxations and LP bounds for orthogonal packing"']:
 rows.append({'source':'HAL official search API','query':q,'note':'Metadata/fulltext lookup; first two have metadata only, last has 0 results.'})
(root/'查询.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print('query calls',len(rows))
