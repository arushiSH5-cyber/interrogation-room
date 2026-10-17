% =====================================================================
% mystery.pl -- "Death at Ashford Manor" (hand-written Stage 1 mystery)
%
% This file holds DATA only: who exists, what physically happened,
% and what each suspect told the detective. All reasoning lives in
% rules.pl and contradictions.pl, so a new mystery can be swapped in
% without touching the logic.
%
% Conventions
%   - Names are lowercase atoms: butler, library, candlestick.
%   - Hours are integers on a 24-hour clock: 21 means 9 pm.
%   - location(Person, Room, Hour) means "Person was in Room at Hour".
% =====================================================================

% Later stages add testimony while the game runs (assertz/1), so these
% predicates must be dynamic instead of fixed at load time.
:- dynamic says/2, evidence/2.

% --- The cast ---------------------------------------------------------
person(lord_ashford).
person(butler).
person(maid).
person(gardener).
person(niece).

victim(lord_ashford).

% --- The house --------------------------------------------------------
room(library).
room(kitchen).
room(garden).
room(study).

% --- What physically happened (ground truth the detective knows) ------
% murder(Victim, Room, Hour)
murder(lord_ashford, library, 21).

% weapon_kept(Weapon, Room): where the murder weapon is normally kept.
weapon_kept(candlestick, study).

% motive(Person, Reason)
motive(niece, inheritance).
motive(butler, unpaid_wages).

% --- Physical evidence ------------------------------------------------
% evidence(Fact, Item): Item proves Fact. Evidence cannot lie.
evidence(location(niece, study, 20), torn_glove).

% --- Testimony ----------------------------------------------------------
% says(Speaker, Fact): Speaker claims Fact is true. Testimony CAN lie.
% The niece is the culprit; her two statements below are lies.
says(butler,   location(butler, kitchen, 21)).
says(maid,     location(maid, kitchen, 21)).
says(maid,     location(butler, kitchen, 21)).      % alibi for the butler
says(maid,     location(niece, library, 21)).       % saw her go in
says(gardener, location(gardener, garden, 21)).
says(niece,    location(niece, garden, 21)).        % LIE
says(niece,    location(niece, kitchen, 20)).       % LIE
