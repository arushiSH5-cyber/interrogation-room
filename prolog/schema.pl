% =====================================================================
% schema.pl -- the predicates a scenario (mystery) is made of.
%
% Declaring them dynamic lets Python (src/engine.py) wipe one mystery
% and assert the next one while the program runs. The reasoning files
% (rules.pl, contradictions.pl, ...) only ever READ these predicates,
% so they work for any scenario.
% =====================================================================

% The case file (what the detective knows)
:- dynamic person/1, room/1, victim/1, murder/3, weapon_kept/2,
           motive/2, evidence/2.

% Testimony collected during play (grows as suspects talk)
:- dynamic says/2.

% The answer key (hidden from the player; only verify.pl reads it)
:- dynamic culprit/1, true_location/3, saw/4, cover_story/3.

% Clauses for one scenario may be spread over a file in any order.
:- discontiguous person/1, room/1, evidence/2, says/2, motive/2,
                 true_location/3, saw/4, cover_story/3.
