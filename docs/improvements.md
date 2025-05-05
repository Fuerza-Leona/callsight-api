
## Database

Some improvements that we could implement

![](assets/postgres%20-%20public.png)

**Messages not connected to participants through ids**

Shouldn't `messages` be connected to the `participants` table in some way? Since all messages come from participants? Why use non-key `speaker` attribute?

Right now, our app only shows text messages in bubbles depending on the role of the speaker (agent of client). But what if we wanted to store the actual person who said the message for other future features, like showing the speaker's name next to the message? Or other forms of analysis?

**Non-user participant identifier across conversations**

Say that at first we couldn't identify a participant in multiple conversations as a user of the platform. This means that the entry of said participant across multiple conversations repeatedly has `user_id = NULL`. If the participant later wanted to create an account in the platform how can we connect him with his previous conversations appearances?

Say we designed it that way because we trust our custom upload conversation file and manual people matching forms to never have `user_id  = NULL`. If that is the case, what if we wanted to introduce participant identification coming from Microsoft Teams, or Google Meet, or any other meetings provider? Could we store that info into our database as is without losing vital metadata?

Can we remove `user_id` from `participants` and instead have another table `people` with some sort of identifiers like email or name, and then another table `participant_people` which connects `participants.participant_id` with `people.person_id`? Then we could create an additional table for external connections like `external_people(external_id, provider, provider_id, people.person_id)`. Or something like that.

**Naming convention**

Since we use the word `conversation` throughout the database, it would be wise to have the same naming convention across the entire codebase. Do we have said convention? Or are we still using other names like calls / meetings / llamadas? Is this a problem with other terms as well?