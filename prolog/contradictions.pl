% =====================================================================
% contradictions.pl -- find statements that cannot all be true,
% and explain WHY with a small, readable proof.
%
% Vocabulary
%   A "claim" wraps a fact together with where it came from:
%     said(Speaker, Fact)      -- testimony (may be a lie)
%     evidence(Fact, Item)     -- physical evidence (trusted)
% =====================================================================

% claim(?Claim): every piece of testimony and evidence is a claim.
claim(said(Speaker, Fact)) :-
    says(Speaker, Fact).
claim(evidence(Fact, Item)) :-
    evidence(Fact, Item).

% fact_of(+Claim, -Fact): unwrap the fact inside a claim.
fact_of(said(_Speaker, Fact), Fact).
fact_of(evidence(Fact, _Item), Fact).

% conflict(+Fact1, +Fact2, -Reason)
% The two facts cannot both be true; Reason names the broken rule.
% Rule "one place at a time": the same person (P) at the same hour (H)
% in two different rooms. Reusing P and H in both heads forces them
% to match -- that check is done by unification, not by extra code.
% Add new kinds of contradiction as new conflict/3 clauses.
conflict(location(P, Room1, H), location(P, Room2, H),
         one_place_at_a_time(P, H, Room1, Room2)) :-
    Room1 \== Room2.

% contradiction(?ClaimA, ?ClaimB)
% Two claims whose facts conflict. Prolog backtracks through every
% pair of claims; the @< test keeps each pair once (not as A-B and B-A).
contradiction(ClaimA, ClaimB) :-
    claim(ClaimA),
    claim(ClaimB),
    ClaimA @< ClaimB,
    fact_of(ClaimA, FactA),
    fact_of(ClaimB, FactB),
    conflict(FactA, FactB, _Reason).

% verdict(+ClaimA, +ClaimB, -Verdict): who is to blame?
% Evidence beats testimony; two witnesses disagreeing is a tie; one
% witness disagreeing with themselves is a self-contradiction.
verdict(evidence(_, _), said(S, _), lie_by(S)).
verdict(said(S, _), evidence(_, _), lie_by(S)).
verdict(said(S, _), said(S, _), self_contradiction(S)).
verdict(said(S1, _), said(S2, _), one_of_them_lies(S1, S2)) :-
    S1 \== S2.
% Should never happen in a well-formed mystery, but explain/3 must not
% silently fail if it does.
verdict(evidence(_, _), evidence(_, _), inconsistent_evidence).

% explain(?ClaimA, ?ClaimB, -Proof)
% Proof is a list of steps a person can read top to bottom:
% the two claims, the rule they break, and the verdict.
explain(ClaimA, ClaimB, Proof) :-
    contradiction(ClaimA, ClaimB),
    fact_of(ClaimA, FactA),
    fact_of(ClaimB, FactB),
    conflict(FactA, FactB, Reason),
    verdict(ClaimA, ClaimB, Verdict),
    Proof = [ claim(ClaimA),
              claim(ClaimB),
              breaks(Reason),
              verdict(Verdict) ].

% proven_liar(?Speaker): physical evidence contradicts Speaker.
proven_liar(Speaker) :-
    explain(_, _, Proof),
    member(verdict(lie_by(Speaker)), Proof).

% show_contradictions/0: print every contradiction with its proof.
% forall/2 means "for every solution of the first goal, run the second".
show_contradictions :-
    (   contradiction(_, _)
    ->  forall(explain(_, _, Proof), print_proof(Proof))
    ;   writeln('No contradictions found.')
    ).

print_proof(Proof) :-
    writeln('--- Contradiction ---'),
    forall(member(Step, Proof), format("  ~w~n", [Step])).
