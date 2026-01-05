Merry-Go-Round (MGR) App — Technical Developer Documentation
1. Overview

The Merry-Go-Round (MGR) application manages collaborative saving groups in which users contribute fixed amounts at set intervals. Depending on the group type, members either receive pooled payouts rotationally or at the end of the cycle (marathon model).

This document provides a complete technical breakdown of:

Data models

Business logic

Services architecture

View-layer behaviour

Lifecycle of rounds, payouts, and contributions

Error handling rules

Interactions with the Wallet system

Security & permission assumptions

Everything described below is based on the actual application code.

2. Data Model Architecture
2.1. Round

Represents a savings group.

Key fields:

name

amount (required contribution per cycle)

frequency (daily/weekly/monthly)

status (active, completed, closed)

group_type (public/private)

round_type (rotational/marathon)

max_members

duration_days (auto-calculated based on frequency × cycles)

owner (creator of the round)

Responsibilities:

Defines the structure & rules of the savings cycle.

Tracks total contributions.

Holds metadata for duration, frequency, type, and member capacity.

Used to serialize group information for listing and detail views.

2.2. RoundMember

Represents a user participating in a round.

Fields include:

round

user

position (payout order for rotational groups)

remaining_contributions

has_received_payout

initial_deposit

total_contributed

last_contribution_date

Responsibilities:

Tracks each member's progress.

Determines payout position in rotational rounds.

Stores contribution history summary for fast access.

2.3. Contribution

Represents a single deposit by a member.

Fields:

member

amount

date

is_initial

Used for:

Historical logs

Payment schedule calculations

Payout eligibility validation

2.4. Payout

Represents disbursement of pooled funds.

Fields:

round

member

amount

date

is_completed

Used only after payout lifecycle triggers.

2.5. RoundInvite

Tracks invited users to private groups.

Fields:

round

email_or_phone

status (pending/accepted/expired)

2.6. RoundMessage

Message board for group chat.

2.7. MGRWalletTransaction

Tracks money movements between:

User Wallet

MGR pool

Payout disbursements

Escrow logic (if present)

2.8. RoundActivityLog

Auditable log of all events:

Join

Contribution

Missed payments

Payout release

Round completion

3. Business Logic Summary
3.1. Round Types
Rotational

Each cycle, one member receives the full pool.

position determines payout order.

Service ensures:

Member has contributed up to the current cycle.

Member has not previously received a payout.

Payout automatically moves to next candidate.

Marathon

No early payouts.

Every member contributes for the full duration.

At end of cycle:

Everyone is paid back

Plus earned interest

3.2. Contribution Lifecycle

When a user contributes:

Validate membership.

Validate amount equals round.amount.

Create Contribution instance.

Update:

RoundMember.total_contributed

remaining_contributions

last_contribution_date

Log activity.

Trigger payout check (rotational only).

3.3. Payout Lifecycle

For rotational rounds:

Identify current slot (cycle index).

Identify eligible member (position matches cycle).

Check:

User is fully paid up to that cycle.

Release fund:

Create a Payout

Debit pool

Credit member wallet

Update:

RoundMember.has_received_payout = True

If all members completed:

Mark round completed.

For marathon:

All payouts issued only at end of round duration.

3.4. Membership Limits

Public rounds: first-come-first-serve.

Private rounds: invitation required.

When max_members reached → round is locked.

4. Services Layer (services.py)

This layer contains pure business logic reused across multiple views.

4.1. create_round

Creates a new round instance with:

Calculated duration_days

Validated parameters

Owner set as creator

4.2. join_round

Joins a user into a round:

Validates not already joined

Ensures capacity exists

Assigns payout position

Creates RoundMember

4.3. make_contribution

Central logic for contributions:

Validates payment amount

Creates Contribution

Updates RoundMember

Triggers payout logic if required

4.4. check_and_process_payout

Handles rotational payouts:

Determines if round is eligible for payout

Selects correct member

Processes wallet movements

4.5. complete_round_if_eligible

Called whenever contributions or payouts update:

Marks round complete if all members:

Finished contributions

Received payouts (rotational)

4.6. send_invite & accept_invite

Manage invite-only private rounds.

5. View Layer (views.py)

This layer handles:

HTTP requests

Template rendering

Invoking services

User permissions

Form validation

Redirects

Serialization for API endpoints

5.1. Dashboard Views
dashboard_view

Displays user information

Lists active rounds

Shows contribution summaries

Displays wallet balance

5.2. Round Creation & Joining
create_round_view

Renders creation form

Submits through service create_round()

join_round_view

Handles joining of public and private rounds

Updates dashboard and redirects appropriately

5.3. Round Details
round_detail_view

Displays:

Round summary

Member table

Contribution logs

Payout logs

Remaining cycles

Chat/messages

5.4. Contribution Views
contribute_view

Deducts from wallet

Calls make_contribution()

stk_sim_view

Mock STK push simulation for test environment.

5.5. Payout Views
trigger_payout_view

Admin/automated payout logic execution.

5.6. Invitational Workflow
invite_member_view

Sends invites via email/phone.

accept_invite_view

Joins invited user.

5.7. Messaging & Activity Logging
post_message_view

Creates a group chat entry.

activity_log_view

Displays chronological actions.

6. Round Lifecycle Summary (Technical)
1. Round created

→ duration calculated
→ owner assigned

2. Member joins

→ position assigned (rotational)
→ initial RoundMember created

3. Member contributes

→ Contribution saved
→ Wallet deducted
→ RoundMember updated
→ Payout triggered if needed

4. Payout triggered (rotational)

→ Eligible member identified
→ Wallet credited
→ Logs updated

Payouys are less the set tax rate. The tax rate is on the interest earned. 

5. Marathon round ends

→ Interest calculated
→ Group payout processed simultaneously

6. Round completion

→ status changed to COMPLETED
→ visible in finished rounds UI

7. Error Handling & Validation
Common checks:

Round is active

Member exists

Correct contribution amount

Invitation validity

Wallet balance

Payout already completed

User is allowed to view round

8. External Systems Interactions
Wallet Integration:

Contribution → debit from wallet

Payout → credit to wallet

All wallet operations logged in MGRWalletTransaction

9. Security & Access Rules

Only members can view round details

Only owner can invite in private groups

Only rightful member receives payout

Round becomes read-only after completion

Celery handles all the tasks 