% =====================================================================
% detective.pl -- turn contradictions into an accusation.
%
% contradictions.pl says WHICH statements clash. This file decides WHO
% the logic engine accuses of lying, so the Prolog checker can be scored
% against other detectors in the Stage 7 evaluation.
% =====================================================================

% accused(?Speaker): the logic believes Speaker lied, because ...
% ... physical evidence contradicts them,
accused(Speaker) :-
    proven_liar(Speaker).
% ... they contradicted themselves,
accused(Speaker) :-
    explain(_, _, Proof),
    memberchk(verdict(self_contradiction(Speaker)), Proof).
% ... or two witnesses disagree and Speaker is the one who also has
% motive, means and opportunity (the tie-breaker).
accused(Speaker) :-
    explain(_, _, Proof),
    memberchk(verdict(one_of_them_lies(A, B)), Proof),
    ( Speaker = A ; Speaker = B ),
    prime_suspect(Speaker).

% accused_list(-Speakers): sorted, without duplicates ([] if nobody).
accused_list(Speakers) :-
    findall(S, accused(S), Found),
    sort(Found, Speakers).
