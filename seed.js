const mongoose = require('mongoose');
const Project = require('./models/Project');
require('dotenv').config();

const sampleProjects = [
    {
        name: 'BECO TYSONS',
        projectNumber: '#21000',
        manager: 'Gary Golden',
        status: 'Active',
        progress: 65,
        deadline: new Date('2025-11-01'),
        totalManHours: 2000,
        desiredManPower: 6,
        efficiency: 0.60
    },
    {
        name: 'MAX9',
        projectNumber: '#21007',
        manager: 'John Dennis',
        status: 'Active',
        progress: 55,
        deadline: new Date('2025-11-01'),
        totalManHours: 1500,
        desiredManPower: 4,
        efficiency: 0.75
    }
];

async function seedDatabase() {
    try {
        await mongoose.connect(process.env.MONGODB_URI);
        console.log('MongoDB connected successfully for seeding.');

        // Clear existing projects to prevent duplicates
        await Project.deleteMany({});
        console.log('Cleared existing projects.');

        // Insert the new sample projects
        await Project.insertMany(sampleProjects);
        console.log('Sample projects have been added!');
        
        console.log('\n--- Projects seeded successfully! ---');

        mongoose.connection.close();
        console.log('MongoDB connection closed.');
    } catch (error) {
        console.error('Error seeding database:', error);
        process.exit(1);
    }
}

seedDatabase();