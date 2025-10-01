import express, { Request, Response } from 'express';
import ProjectModel, { ProjectDocument } from '../models/Project';

const router = express.Router();

// Get all projects
router.get('/', async (req: Request, res: Response) => {
  try {
    const projects = await ProjectModel.find().sort({ createdAt: -1 });
    res.json(projects);
  } catch (error) {
    console.error('Error fetching projects:', error);
    res.status(500).json({ error: 'Error fetching projects' });
  }
});

// Get single project by ID
router.get('/:id', async (req: Request, res: Response) => {
  try {
    const project = await ProjectModel.findById(req.params.id);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }
    res.json(project);
  } catch (error) {
    console.error('Error fetching project:', error);
    res.status(500).json({ error: 'Error fetching project' });
  }
});

// Create new project
router.post('/', async (req: Request, res: Response) => {
  try {
    const { name, manager, status, progress, deadline, team, scope, phases } = req.body;

    const project = new ProjectModel({
      name,
      manager,
      status: status || 'Planning',
      progress: progress || 0,
      deadline,
      team: team || [],
      scope: scope || '',
      phases: phases || [],
    });

    await project.save();
    res.status(201).json({
      message: 'Project created successfully',
      project,
    });
  } catch (error) {
    console.error('Error creating project:', error);
    res.status(500).json({ error: 'Error creating project' });
  }
});

// Update project
router.put('/:id', async (req: Request, res: Response) => {
  try {
    const project = await ProjectModel.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );

    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    res.json({
      message: 'Project updated successfully',
      project,
    });
  } catch (error) {
    console.error('Error updating project:', error);
    res.status(500).json({ error: 'Error updating project' });
  }
});

// Update project progress
router.patch('/:id/progress', async (req: Request, res: Response) => {
  try {
    const { progress } = req.body;

    if (progress < 0 || progress > 100) {
      return res.status(400).json({ error: 'Progress must be between 0 and 100' });
    }

    const project = await ProjectModel.findByIdAndUpdate(
      req.params.id,
      { progress },
      { new: true }
    );

    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    res.json({
      message: 'Progress updated successfully',
      project,
    });
  } catch (error) {
    console.error('Error updating progress:', error);
    res.status(500).json({ error: 'Error updating progress' });
  }
});

// Add team member to project
router.post('/:id/team', async (req: Request, res: Response) => {
  try {
    const { name, role } = req.body;

    const project = await ProjectModel.findById(req.params.id);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    project.team.push({ name, role });
    await project.save();

    res.json({
      message: 'Team member added successfully',
      project,
    });
  } catch (error) {
    console.error('Error adding team member:', error);
    res.status(500).json({ error: 'Error adding team member' });
  }
});

// Remove team member from project
router.delete('/:id/team/:memberId', async (req: Request, res: Response) => {
  try {
    const project = await ProjectModel.findById(req.params.id);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    project.team = project.team.filter(
      (member: any) => member._id?.toString() !== req.params.memberId
    );
    await project.save();

    res.json({
      message: 'Team member removed successfully',
      project,
    });
  } catch (error) {
    console.error('Error removing team member:', error);
    res.status(500).json({ error: 'Error removing team member' });
  }
});

// Delete project
router.delete('/:id', async (req: Request, res: Response) => {
  try {
    const project = await ProjectModel.findByIdAndDelete(req.params.id);

    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    res.json({ message: 'Project deleted successfully' });
  } catch (error) {
    console.error('Error deleting project:', error);
    res.status(500).json({ error: 'Error deleting project' });
  }
});

export default router;