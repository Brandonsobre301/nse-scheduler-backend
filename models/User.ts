/*This file tells your app what information a user should have and how to store it in the database.*/
import { Schema, model, InferSchemaType, HydratedDocument} from 'mongoose';



const UserSchema = new Schema(
    {
    name: { type: String, required: true }, 
    email: { type: String, unique: true, required: true  },
    password: { type: String, required: true },
    dateOfBirth: { type: Date},

},
{timestamps:true }
);

// Infer the TS type from the schema
export type User = InferSchemaType<typeof UserSchema>;
export type UserDocument = HydratedDocument<User>;

const UserModel = model<User>('User', UserSchema);

export default UserModel;
