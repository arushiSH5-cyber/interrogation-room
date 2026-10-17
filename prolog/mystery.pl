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

% schema.pl declares every scenario predicate dynamic, so later stages
% can add testimony while the game runs (assertz/1) or swap mysteries.
:- ensure_loaded(schema).

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

% --- Answer key ---------------------------------------------------------
% What REALLY happened. The game logic (rules.pl, contradictions.pl)
% never reads these facts; only verify.pl does, to check that the
% mystery is fair and has exactly one solution (Stage 6).
culprit(niece).

% true_location(Person, Room, Hour)
true_location(butler,   kitchen, 20).
true_location(butler,   kitchen, 21).
true_location(maid,     kitchen, 20).
true_location(maid,     kitchen, 21).
true_location(gardener, garden,  20).
true_location(gardener, garden,  21).
true_location(niece,    study,   20).    % fetching the candlestick
true_location(niece,    library, 21).    % the murder
true_location(lord_ashford, library, 20).
true_location(lord_ashford, library, 21).

% saw(Witness, Person, Room, Hour): things a witness noticed.
saw(maid, niece, library, 21).           % from the hallway

% cover_story(Culprit, Room, Hour): the lie the culprit will tell.
cover_story(niece, kitchen, 20).
cover_story(niece, garden,  21).
