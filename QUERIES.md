# Stage 1 query cheat sheet

Start Prolog with the mystery loaded:

```bash
swipl prolog/load.pl
```

Type each query after the `?-` prompt. **End every query with a period.**
When Prolog shows one answer and waits, press `;` for the next answer or
Enter to stop. `halt.` quits.

## 1. Look at the facts

```prolog
?- person(X).                         % press ; to see each person
?- says(niece, What).                 % everything the niece claimed
?- says(Who, location(niece, R, H)).  % who placed the niece where?
```

## 2. Detective rules

```prolog
?- had_motive(P).
?- had_opportunity(P).
?- had_means(P).
?- prime_suspect(P).                  % P = niece.
?- prime_suspects(L).                 % L = [niece].
```

## 3. Contradictions

```prolog
?- contradiction(A, B).               % press ; for the second one
?- explain(A, B, Proof).
?- proven_liar(Who).
?- show_contradictions.               % pretty-prints every proof
```

## 4. Add testimony live (this is what the game will do in Stage 5)

```prolog
?- assertz(says(butler, location(butler, garden, 21))).
?- show_contradictions.               % two new ones: butler vs himself, and maid vs butler
?- retract(says(butler, location(butler, garden, 21))).
```

## 5. Watch Prolog think

```prolog
?- trace, prime_suspect(P).
```

Press Enter ("creep") to step through each goal and watch unification
and backtracking happen. `notrace.` turns it off.
