/*This file sets up and manages the connection between your app and your MongoDB database.*/
import mongoose from 'mongoose';
import dotenv from 'dotenv';
dotenv.config();
mongoose.set('debug', true);

const mongoUri = process.env.MONGODB_URI || 'mongodb://localhost:27017/nse_scheduler';

mongoose
  .connect(mongoUri)
.then(() => {
      console.log("MongoDB connected successfully");
})
.catch((err) => {
  console.log('MongoDB connection error:', err);
});

export default mongoose;