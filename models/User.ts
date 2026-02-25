/*This file tells your app what information a user should have and how to store it in the database.*/
import { Schema, model, HydratedDocument } from 'mongoose';

export interface User {
  name: string;
  email: string;
  password: string;
  dateOfBirth?: Date;
  role: 'admin' | 'manager' | 'viewer'; // Add this
  createdAt?: Date;
  updatedAt?: Date;
}

export type UserDocument = HydratedDocument<User>;

const userSchema = new Schema<User>({
  name: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  dateOfBirth: Date,
  role: { 
    type: String, 
    enum: ['admin', 'manager', 'viewer'], 
    default: 'viewer' 
  },
}, { timestamps: true });

const UserModel = model<User>('User', userSchema);
export default UserModel;
