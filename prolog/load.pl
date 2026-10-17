% load.pl -- load the Stage 1 mystery together with all the logic.
% Usage:  swipl prolog/load.pl
:- ensure_loaded(mystery).
:- ensure_loaded(rules).
:- ensure_loaded(contradictions).
:- ensure_loaded(detective).
