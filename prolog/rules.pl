% =====================================================================
% rules.pl -- who COULD have done it?
%
% Classic detective reasoning: a prime suspect needs opportunity
% (at the scene at the time), means (access to the weapon) and motive.
% Each rule is a small question Prolog answers by searching the facts
% in mystery.pl; prime_suspect/1 just combines the three.
% =====================================================================

% placed_at(?Person, ?Room, ?Hour)
% Someone's statement or a piece of evidence puts Person in Room at Hour.
% Two clauses = two ways to be true. Prolog tries the first, then
% backtracks into the second to find more answers.
placed_at(Person, Room, Hour) :-
    says(_AnySpeaker, location(Person, Room, Hour)).
placed_at(Person, Room, Hour) :-
    evidence(location(Person, Room, Hour), _AnyItem).

% had_opportunity(?Person)
% Person was placed in the murder room at the murder hour.
% Sharing the variables Room and Hour between the two goals is
% unification at work: both goals must agree on the same values.
had_opportunity(Person) :-
    murder(Victim, Room, Hour),
    placed_at(Person, Room, Hour),
    Person \== Victim.

% had_means(?Person)
% Person was placed, at any hour, in the room where the weapon is kept.
had_means(Person) :-
    weapon_kept(_Weapon, Room),
    placed_at(Person, Room, _AnyHour).

% had_motive(?Person)
had_motive(Person) :-
    motive(Person, _Reason).

% prime_suspect(?Person)
% Opportunity, means and motive all hold. A conjunction (commas) means
% Prolog backtracks through candidates until all three succeed.
prime_suspect(Person) :-
    had_opportunity(Person),
    had_means(Person),
    had_motive(Person).

% prime_suspects(-People)
% All prime suspects as a sorted list with no duplicates
% ([] if there are none -- findall never fails, unlike setof).
prime_suspects(People) :-
    findall(P, prime_suspect(P), Found),
    sort(Found, People).
