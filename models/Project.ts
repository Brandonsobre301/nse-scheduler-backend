
import { Schema, model, Types, HydratedDocument} from 'mongoose';


export interface TeamMember {
    name: string;
    role: string;
}

export interface Milestone {
    name: string;
    date?: Date;
}

export type PhaseStatus = 'Planning' | 'Active' | 'At Risk' | 'Delayed' | 'Done';

export interface Phase {
    name: string;
    startDate?: Date;
    endDate?: Date;
    status: PhaseStatus;
    progress: number; // percentage 0-100
    assignees: string[];
    milestones: Milestone[];

}

export interface Project {

    name: string;
    projectNumber: string;
    manager: string;
    status?: string;
    progress?: number;
    deadline?: Date;

    team: TeamMember[];
    phases: Phase[];

    //Calculator
    totalManHours?: number;
    desiredManpower?: number;
    efficiency?: number;
    targetDurationWeeks?: number;

    createdAt?: Date;
    UpdatedAt?: Date;
}

export type ProjectDocument = HydratedDocument<Project>;

const TeamMemberSchema = new Schema<TeamMember>(
    {
        name: {type: String, required: true},
        role: {type: String, required: true},
    
    },
    { _id: true }
);

const PhaseSchema = new Schema<Phase>(
    {
        name: { type: String, required: true },
        startDate: Date,
        endDate: Date,
        status: {
            type: String,
            enum: ['Planning', 'Active', 'At Risk', 'Delayed', 'Done'],
            default: 'Planning',
        },
        progress: {type: Number, min: 0, max: 100, default: 0 },    
        assignees: { type: [String], default: [] },
        milestones: {
            type: [{ name: String, date: Date}],
            ddefault: [],
        },
    },
    { _id: true }
);  
const projectSchema = new Schema<Project>(
    {
        name: { type: String, required: true },
        projectNumber: {type: String, required: true},
        manager:{ type: String, required: true },
        status: { type: String, default: 'Active' },    
        progress: { type: Number, default:0 },  
        deadline: Date,

        team:{ type: [TeamMemberSchema], default: []},
        phases: { type: [PhaseSchema], default: []},

        totalManHours: { type: Number, default: 0},
        desiredManpower: { type: Number, default: 1},
        efficiency: { type: Number, default: 0.8},
        targetDurationWeeks: { type: Number, default: 0, min: 0},   

    },
    {timestamps: true } 
);

const ProjectModel = model<Project>('Project', projectSchema);
export default ProjectModel;