% test_prolog.pl -- unit tests for the Stage 1 Prolog logic (plunit).
% Run:  swipl -g run_tests -t halt tests/test_prolog.pl
:- use_module(library(plunit)).
:- ensure_loaded('../prolog/load').

:- begin_tests(rules).

test(only_niece_is_prime_suspect) :-
    prime_suspects([niece]).

test(butler_has_motive_but_no_opportunity, [fail]) :-
    had_opportunity(butler).

:- end_tests(rules).

:- begin_tests(contradictions).

test(finds_exactly_two) :-
    findall(A-B, contradiction(A, B), Pairs),
    length(Pairs, 2).

test(evidence_proves_niece_lied, [nondet]) :-
    proven_liar(niece).

test(honest_maid_is_not_a_proven_liar, [fail]) :-
    proven_liar(maid).

% Two people agreeing is not a contradiction (maid and butler both
% place the butler in the kitchen at 21).
test(agreeing_claims_do_not_conflict, [fail]) :-
    contradiction(said(butler, location(butler, kitchen, 21)),
                  said(maid,   location(butler, kitchen, 21))).

% Edge case: a speaker contradicting themselves. We add a statement,
% check it, and always remove it again (cleanup) so other tests are
% unaffected. The `user:` prefix matters: plunit runs each test inside
% its own module, and without the prefix assertz would create a private
% copy of says/2 there instead of adding to the game's facts.
test(self_contradiction,
     [ setup(assertz(user:says(gardener, location(gardener, study, 21)))),
       cleanup(retract(user:says(gardener, location(gardener, study, 21)))),
       nondet ]) :-
    explain(_, _, Proof),
    memberchk(verdict(self_contradiction(gardener)), Proof).

:- end_tests(contradictions).

:- begin_tests(detective).

% The maid/niece tie is broken by prime_suspect/1, and the glove proves
% the niece lied, so the niece (and only the niece) is accused.
test(accuses_only_the_niece) :-
    accused_list([niece]).

test(honest_maid_not_accused, [fail]) :-
    accused(maid).

:- end_tests(detective).
