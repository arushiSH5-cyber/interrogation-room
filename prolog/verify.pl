% =====================================================================
% verify.pl -- is a mystery FAIR? (used before play, Stage 6)
%
% Reads the hidden answer key (culprit/1, true_location/3, saw/4,
% cover_story/3) and lists every problem it can find. A mystery is
% playable only when verify_mystery([]) holds:
%   - the story is physically consistent,
%   - the culprit really did it (at the scene, had the weapon, motive),
%   - and a perfect interrogation catches the culprit, and only them.
% =====================================================================

suspect(P) :- person(P), \+ victim(P).

% --- What a perfect interrogation would hear --------------------------
% An honest suspect reports where they were, who was in the same room
% at the same hour, and anything they specifically saw.
honest_claim(S, location(S, R, H)) :- true_location(S, R, H).
honest_claim(S, location(P, R, H)) :-
    true_location(S, R, H), true_location(P, R, H), P \== S.
honest_claim(S, location(P, R, H)) :- saw(S, P, R, H).

% The culprit only ever repeats the cover story.
expected_claim(S, Fact) :- suspect(S), \+ culprit(S), honest_claim(S, Fact).
expected_claim(C, location(C, R, H)) :- culprit(C), cover_story(C, R, H).

% simulated(+Goal): run Goal as if every suspect had been asked about
% everything, then remove that pretend testimony again.
% setup_call_cleanup/3 guarantees the cleanup even if Goal fails.
simulated(Goal) :-
    findall(says(S, F), expected_claim(S, F), Found),
    sort(Found, Claims),
    exclude(call, Claims, New),          % keep real testimony untouched
    setup_call_cleanup(maplist(assertz, New),
                       once(Goal),
                       maplist(retract, New)).

% --- problem(-Problem): one clause per thing that can be wrong ----------
problem(not_exactly_one_culprit) :-
    findall(C, culprit(C), Cs), length(Cs, N), N =\= 1.
problem(culprit_not_a_suspect(C)) :-
    culprit(C), \+ suspect(C).
problem(two_places_at_once(P, H)) :-
    true_location(P, R1, H), true_location(P, R2, H), R1 @< R2.
problem(victim_not_at_scene(V)) :-
    murder(V, R, H), \+ true_location(V, R, H).
problem(culprit_not_at_scene(C)) :-
    culprit(C), murder(_, R, H), \+ true_location(C, R, H).
problem(innocent_witnessed_murder(P)) :-        % they would just say so
    murder(_, R, H), true_location(P, R, H), suspect(P), \+ culprit(P).
problem(culprit_never_near_weapon(C)) :-
    culprit(C), weapon_kept(_, R), \+ true_location(C, R, _).
problem(culprit_has_no_motive(C)) :-
    culprit(C), \+ motive(C, _).
problem(false_evidence(Item)) :-
    evidence(location(P, R, H), Item), \+ true_location(P, R, H).
problem(false_sighting(W, P, R, H)) :-
    saw(W, P, R, H), \+ true_location(P, R, H).
problem(cover_story_tells_no_lie(C)) :-
    culprit(C), \+ ( cover_story(C, R, H), \+ true_location(C, R, H) ).
problem(no_alibi_for_murder_hour(C)) :-
    culprit(C), murder(_, _, H), \+ cover_story(C, _, H).
problem(cover_story_two_places(C, H)) :-
    cover_story(C, R1, H), cover_story(C, R2, H), R1 @< R2.
% Solvability: run the detective rules on the perfect interrogation.
problem(not_exactly_one_prime_suspect(Ps)) :-
    simulated(prime_suspects(Ps)),
    \+ ( culprit(C), Ps == [C] ).
problem(culprit_not_caught(C)) :-
    culprit(C), simulated(accused_list(L)), \+ memberchk(C, L).
problem(innocent_accused(S)) :-
    simulated(accused_list(L)), member(S, L), \+ culprit(S).

% verify_mystery(-Problems): sorted list; [] means the mystery is fair.
verify_mystery(Problems) :-
    findall(P, problem(P), Found),
    sort(Found, Problems).
