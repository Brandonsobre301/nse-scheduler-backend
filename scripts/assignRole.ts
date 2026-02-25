import mongoose from 'mongoose';
import User from '../models/User';
import dotenv from 'dotenv';   

dotenv.config();

// Define roles
interface RoleAssignment {
    email: string;
    role: 'admin' | 'manager' | 'viewer';
}

// Assign roles based on email
const roleAssignments: RoleAssignment[] = [
    { email: 'brandonsobre301@gmail.com', role: 'admin' },
    { email: 'Lloun@newspectrumelec.com', role: 'manager' },
    { email: 'dwoode@newspectrumelec.com', role: 'manager' },
    { email: 'viewer@newspectrumelec.com', role: 'viewer' },  

];

async function assignRoles(): Promise<void> {
    try {
        const mongoUri = process.env.MONGODB_URI;

        if (!mongoUri) {
            throw new Error('MONGO_URI is not defined in environment variables');
        }   
        await mongoose.connect(mongoUri);
        console.log('Connected to MongoDB for role assignment\n');
        
        for (const assignment of roleAssignments) {
            const result = await User.updateOne(
                { email: assignment.email }, 
                { $set: { role: assignment.role } }
              );

              if (result.matchedCount === 0) {
                console.log(`No user found with email: ${assignment.email}`);
              } else if (result.modifiedCount === 0) {
                console.log(`User role is already set to: ${assignment.role}`);
              } else {
                console.log(`Assigned role '${assignment.role}' to user with email: ${assignment.email}`);
              }         
            }

        console.log('\nRole assignment process completed.');

        await mongoose.connection.close();
        console.log('Disconnected from MongoDB');
        process.exit(0);
    } catch (error) {
        console.error('Error during role assignment:', error);
        process.exit(1);
    }   
}

assignRoles();