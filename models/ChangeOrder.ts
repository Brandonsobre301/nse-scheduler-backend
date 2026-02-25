import {Schema, model, Types, HydratedDocument, StringExpressionOperatorReturningBoolean} from 'mongoose';

export type ChangeOrderDocument = 'Pending' | 'Approved' | 'Rejected' | 'Voided';

export interface ChangeOrder {
    externalId: string;
    projectId: Types.ObjectId;
    projectNumber?: string;
    status: ChangeOrderDocument;
    manHoursDelta: number;
    note?: string;
    createdAt: Date;
    updatedAt: Date;
}

export type ChangeOrderDocument = HydratedDocument<ChangeOrder>;

const ChangeOrderSchema = new Schema<ChangeOrder>({ 
    externalId: { type: String, required: true, unique: true },
    projectId: { type: Schema.Types.ObjectId, ref: 'Project', required: true },
    projectNumber: { type: String },
    status: { type: String, enum: ['Pending', 'Approved', 'Rejected', 'Voided'], required: true },
    manHoursDelta: { type: Number, required: true },
    note: { type: String },
}, { timestamps: true
})